"""
M14 RAG 索引脚本（正式版）
用途: 扫描 Markdown 文件，embedding 后写入 PG+pgvector
调用:
  python rag_index.py full         # 全量索引（首次或修复）
  python rag_index.py incremental  # 增量索引（只更新变更文件）
  python rag_index.py stats        # 查看索引统计
"""
import os
import re
import sys
import time
import hashlib
import argparse
import psycopg2
import yaml
from pathlib import Path
from openai import OpenAI
from pgvector.psycopg2 import register_vector
from datetime import datetime, timezone

# ── Load Config ─────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
CONFIG_PATH = SCRIPT_DIR.parent / 'config' / 'rag_config.yaml'

with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
    CFG = yaml.safe_load(f)

EMB_CFG = CFG['embedding']
DB_CFG = CFG['database']
IDX_CFG = CFG['indexing']

def get_emb_client():
    api_key = os.environ.get(EMB_CFG['api_key_env'], '')
    if not api_key:
        raise RuntimeError(f"Missing env var: {EMB_CFG['api_key_env']}")
    return OpenAI(api_key=api_key, base_url=EMB_CFG['base_url'])

def get_pg_conn():
    password = os.environ.get(DB_CFG.get('password_env', ''), DB_CFG.get('password', ''))
    conn = psycopg2.connect(
        host=DB_CFG['host'], port=DB_CFG['port'],
        user=DB_CFG['user'], password=password,
        dbname=DB_CFG['dbname'], connect_timeout=10
    )
    register_vector(conn)
    return conn

# ── Text Processing ─────────────────────────────────
def parse_frontmatter(text):
    meta = {}
    match = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
    if match:
        for line in match.group(1).split('\n'):
            line = line.strip()
            if ':' in line and not line.startswith('#') and not line.startswith('-'):
                key, _, val = line.partition(':')
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key in ('doc_status', 'domain', 'tier', 'type', 'status'):
                    meta[key] = val
    return meta

def infer_layer(filepath, scan_config):
    """Infer prompt_knowledge_layer from file path and scan config."""
    fp = str(filepath).replace('\\', '/')
    for entry in scan_config:
        entry_path = entry['path'].replace('\\', '/')
        if fp.startswith(entry_path):
            return entry['layer']
    return 'unknown'

def chunk_text(text, max_chars):
    text = re.sub(r'^---\s*\n.*?\n---\s*\n', '', text, flags=re.DOTALL)
    if not text.strip():
        return []
    paragraphs = re.split(r'\n{2,}', text)
    chunks = []
    current = ''
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) + 2 > max_chars and current:
            chunks.append(current.strip())
            current = para
        else:
            current = current + '\n\n' + para if current else para
    if current.strip():
        chunks.append(current.strip())
    return chunks if chunks else [text[:max_chars]]

def file_hash(filepath):
    return hashlib.md5(Path(filepath).read_bytes()).hexdigest()

def batch_embed(client, texts, batch_size):
    all_embeddings = []
    total_batches = (len(texts) + batch_size - 1) // batch_size
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        try:
            resp = client.embeddings.create(
                model=EMB_CFG['model'], input=batch, dimensions=EMB_CFG['dimensions']
            )
            for d in resp.data:
                all_embeddings.append(d.embedding)
        except Exception as e:
            print(f'    API error at batch {i//batch_size}, retrying: {e}')
            time.sleep(2)
            resp = client.embeddings.create(
                model=EMB_CFG['model'], input=batch, dimensions=EMB_CFG['dimensions']
            )
            for d in resp.data:
                all_embeddings.append(d.embedding)
        bn = i // batch_size + 1
        if bn % 50 == 0 or bn == total_batches:
            print(f'    Batch {bn}/{total_batches} ({len(all_embeddings)} vectors)')
    return all_embeddings

# ── Index Operations ────────────────────────────────
def scan_files():
    all_files = []
    for entry in IDX_CFG['scan_dirs']:
        scan_path = Path(entry['path'])
        if not scan_path.exists():
            print(f'  WARNING: scan dir not found: {entry["path"]}')
            continue
        for ext in IDX_CFG['file_extensions']:
            for f in scan_path.rglob(f'*{ext}'):
                all_files.append((f, entry))
    return all_files

def run_full_index():
    print('=' * 60)
    print('M14 RAG Index - Full Rebuild')
    print('=' * 60)
    t0 = time.time()

    client = get_emb_client()
    files = scan_files()
    print(f'\n  Scanned {len(files)} files')

    # Process all files
    pending_texts = []
    pending_meta = []
    skipped = 0
    max_chars = IDX_CFG['chunk_max_chars']

    for fpath, entry in files:
        try:
            text = fpath.read_text(encoding='utf-8', errors='ignore').replace('\x00', '')
        except Exception:
            skipped += 1
            continue
        meta = parse_frontmatter(text)
        chunks = chunk_text(text, max_chars)
        if not chunks:
            skipped += 1
            continue
        fhash = file_hash(fpath)
        layer = infer_layer(fpath, IDX_CFG['scan_dirs'])
        for ci, chunk in enumerate(chunks):
            chunk_id = f'{str(fpath)}#chunk_{ci}'
            pending_texts.append(chunk[:2000])
            pending_meta.append((
                chunk_id, str(fpath), ci, chunk[:5000],
                meta.get('doc_status', 'unknown'), meta.get('domain', 'unknown'),
                meta.get('tier', 'unknown'), layer, fhash,
            ))

    print(f'  Chunks to embed: {len(pending_texts)} (skipped {skipped} files)')
    print(f'  Embedding via DashScope...')

    embeddings = batch_embed(client, pending_texts, EMB_CFG['batch_size'])

    # Write to PG
    print(f'  Writing to PG...')
    conn = get_pg_conn()
    cur = conn.cursor()

    upsert_sql = f'''
        INSERT INTO {DB_CFG['table']}
            (id, source_path, chunk_index, content,
             doc_status, domain, tier, prompt_knowledge_layer, file_hash, embedding)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector)
        ON CONFLICT (id) DO UPDATE SET
            content = EXCLUDED.content, embedding = EXCLUDED.embedding,
            doc_status = EXCLUDED.doc_status, domain = EXCLUDED.domain,
            tier = EXCLUDED.tier, prompt_knowledge_layer = EXCLUDED.prompt_knowledge_layer,
            file_hash = EXCLUDED.file_hash, indexed_at = NOW();
    '''

    for i, (meta_tuple, emb) in enumerate(zip(pending_meta, embeddings)):
        cur.execute(upsert_sql, meta_tuple + (emb,))
        if (i + 1) % 500 == 0:
            conn.commit()
            print(f'    Written: {i+1}/{len(embeddings)}')
    conn.commit()

    # Rebuild IVFFlat index
    print('  Rebuilding IVFFlat index...')
    try:
        cur.execute('DROP INDEX IF EXISTS idx_embedding;')
        lists = max(1, int(len(embeddings) ** 0.5))
        cur.execute(f'''
            CREATE INDEX idx_embedding ON {DB_CFG['table']}
            USING ivfflat (embedding vector_cosine_ops) WITH (lists = {lists});
        ''')
        conn.commit()
        print(f'    IVFFlat built (lists={lists})')
    except Exception as e:
        print(f'    IVFFlat failed: {e}')
        conn.rollback()

    conn.close()
    total = time.time() - t0
    print(f'\n  DONE: {len(embeddings)} chunks indexed in {total:.0f}s')

def run_incremental_index():
    print('=' * 60)
    print('M14 RAG Index - Incremental Update')
    print('=' * 60)
    t0 = time.time()

    conn = get_pg_conn()
    cur = conn.cursor()

    # Get existing hashes
    cur.execute(f'SELECT DISTINCT source_path, file_hash FROM {DB_CFG["table"]};')
    existing = {}
    for path, fhash in cur.fetchall():
        existing[path] = fhash

    files = scan_files()
    changed = []
    deleted_paths = set(existing.keys())

    for fpath, entry in files:
        fp = str(fpath)
        deleted_paths.discard(fp)
        try:
            current_hash = file_hash(fpath)
        except Exception:
            continue
        if fp not in existing or existing[fp] != current_hash:
            changed.append((fpath, entry))

    print(f'  Total files: {len(files)}')
    print(f'  Changed/new: {len(changed)}')
    print(f'  Deleted: {len(deleted_paths)}')

    if not changed and not deleted_paths:
        print('  Nothing to update.')
        conn.close()
        return

    # Delete removed files
    if deleted_paths:
        for dp in deleted_paths:
            cur.execute(f"DELETE FROM {DB_CFG['table']} WHERE source_path = %s;", (dp,))
        conn.commit()
        print(f'  Deleted {len(deleted_paths)} stale file entries')

    # Re-index changed files
    if changed:
        client = get_emb_client()
        pending_texts = []
        pending_meta = []
        max_chars = IDX_CFG['chunk_max_chars']

        # First delete old chunks for changed files
        for fpath, entry in changed:
            cur.execute(f"DELETE FROM {DB_CFG['table']} WHERE source_path = %s;", (str(fpath),))
        conn.commit()

        for fpath, entry in changed:
            try:
                text = fpath.read_text(encoding='utf-8', errors='ignore').replace('\x00', '')
            except Exception:
                continue
            meta = parse_frontmatter(text)
            chunks = chunk_text(text, max_chars)
            if not chunks:
                continue
            fhash = file_hash(fpath)
            layer = infer_layer(fpath, IDX_CFG['scan_dirs'])
            for ci, chunk in enumerate(chunks):
                chunk_id = f'{str(fpath)}#chunk_{ci}'
                pending_texts.append(chunk[:2000])
                pending_meta.append((
                    chunk_id, str(fpath), ci, chunk[:5000],
                    meta.get('doc_status', 'unknown'), meta.get('domain', 'unknown'),
                    meta.get('tier', 'unknown'), layer, fhash,
                ))

        if pending_texts:
            embeddings = batch_embed(client, pending_texts, EMB_CFG['batch_size'])
            upsert_sql = f'''
                INSERT INTO {DB_CFG['table']}
                    (id, source_path, chunk_index, content,
                     doc_status, domain, tier, prompt_knowledge_layer, file_hash, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector)
                ON CONFLICT (id) DO UPDATE SET
                    content = EXCLUDED.content, embedding = EXCLUDED.embedding,
                    doc_status = EXCLUDED.doc_status, domain = EXCLUDED.domain,
                    tier = EXCLUDED.tier, prompt_knowledge_layer = EXCLUDED.prompt_knowledge_layer,
                    file_hash = EXCLUDED.file_hash, indexed_at = NOW();
            '''
            for meta_tuple, emb in zip(pending_meta, embeddings):
                cur.execute(upsert_sql, meta_tuple + (emb,))
            conn.commit()
            print(f'  Indexed {len(embeddings)} new chunks from {len(changed)} files')

    conn.close()
    print(f'  DONE in {time.time()-t0:.1f}s')

def run_stats():
    conn = get_pg_conn()
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {DB_CFG['table']};")
    total = cur.fetchone()[0]
    cur.execute(f"SELECT COUNT(DISTINCT source_path) FROM {DB_CFG['table']};")
    files = cur.fetchone()[0]
    cur.execute(f"""
        SELECT prompt_knowledge_layer, COUNT(*), COUNT(DISTINCT source_path)
        FROM {DB_CFG['table']} GROUP BY prompt_knowledge_layer ORDER BY 1;
    """)
    layers = cur.fetchall()
    cur.execute(f"""
        SELECT doc_status, COUNT(*) FROM {DB_CFG['table']}
        GROUP BY doc_status ORDER BY 2 DESC;
    """)
    statuses = cur.fetchall()
    conn.close()

    print(f'M14 RAG Index Stats')
    print(f'  Total chunks: {total}')
    print(f'  Total files:  {files}')
    print(f'\n  By layer:')
    for layer, chunks, fcount in layers:
        print(f'    {layer}: {chunks} chunks / {fcount} files')
    print(f'\n  By doc_status:')
    for status, count in statuses:
        print(f'    {status}: {count}')

# ── CLI ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='M14 RAG Index')
    parser.add_argument('mode', choices=['full', 'incremental', 'stats'], help='Index mode')
    args = parser.parse_args()

    if args.mode == 'full':
        run_full_index()
    elif args.mode == 'incremental':
        run_incremental_index()
    elif args.mode == 'stats':
        run_stats()

if __name__ == '__main__':
    main()
