"""
M14 RAG 检索脚本（正式版）
用途: 从 PG+pgvector 中检索语义相关文档片段
调用: python rag_search.py "<query>" [--caller W1] [--json] [--top-k 5] [--filter-domain X] [--filter-tier X]
     python rag_search.py --stats [--json]   # 查看索引规模统计（不调用 embedding）
"""
import os
import sys
import json
import time
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
SEARCH_CFG = CFG['search']

def get_emb_client():
    api_key = os.environ.get(EMB_CFG['api_key_env'], '')
    if not api_key:
        raise RuntimeError(f"Missing env var: {EMB_CFG['api_key_env']}")
    return OpenAI(api_key=api_key, base_url=EMB_CFG['base_url'])

def get_pg_conn():
    password = os.environ.get(DB_CFG.get('password_env', ''), DB_CFG.get('password', ''))
    conn = psycopg2.connect(
        host=DB_CFG['host'],
        port=DB_CFG['port'],
        user=DB_CFG['user'],
        password=password,
        dbname=DB_CFG['dbname'],
        connect_timeout=10
    )
    register_vector(conn)
    return conn

def embed_query(client, query):
    resp = client.embeddings.create(
        model=EMB_CFG['model'],
        input=[query],
        dimensions=EMB_CFG['dimensions']
    )
    return resp.data[0].embedding

def search(query, caller='manual', top_k=5, filters=None):
    """
    Core search function. Returns RAG_ADVISORY_PAYLOAD dict.
    """
    filters = filters or {}
    t0 = time.time()

    try:
        client = get_emb_client()
        q_emb = embed_query(client, query)
        t_embed = time.time() - t0
    except Exception as e:
        return _error_payload(query, caller, 'EMBEDDING_ERROR', str(e))

    try:
        conn = get_pg_conn()
        cur = conn.cursor()

        # Build WHERE clause
        where_clauses = []
        where_params = []

        # Default: exclude archived
        exclude = filters.get('doc_status_exclude', SEARCH_CFG['default_exclude_status'])
        for status in exclude:
            where_clauses.append(f"doc_status != %s")
            where_params.append(status)

        # Domain filter
        domain_include = filters.get('domain_include', [])
        if domain_include:
            placeholders = ', '.join(['%s'] * len(domain_include))
            where_clauses.append(f"domain IN ({placeholders})")
            where_params.extend(domain_include)

        # Tier filter
        tier_include = filters.get('tier_include', [])
        if tier_include:
            placeholders = ', '.join(['%s'] * len(tier_include))
            where_clauses.append(f"tier IN ({placeholders})")
            where_params.extend(tier_include)

        # Layer filter
        layer_include = filters.get('layer_include', [])
        if layer_include:
            placeholders = ', '.join(['%s'] * len(layer_include))
            where_clauses.append(f"prompt_knowledge_layer IN ({placeholders})")
            where_params.extend(layer_include)

        where_sql = ' AND '.join(where_clauses) if where_clauses else '1=1'
        top_k = min(top_k, SEARCH_CFG['max_top_k'])

        sql = f'''
            SELECT source_path, chunk_index, content,
                   1 - (embedding <=> %s::vector) AS similarity,
                   doc_status, domain, tier, prompt_knowledge_layer
            FROM {DB_CFG['table']}
            WHERE {where_sql}
            ORDER BY embedding <=> %s::vector
            LIMIT {top_k};
        '''
        # Parameter order: sim_calc_vector, WHERE params..., order_vector
        params = [q_emb] + where_params + [q_emb]
        
        t_query = time.time()
        cur.execute(sql, params)
        results = cur.fetchall()
        t_pg = time.time() - t_query

        conn.close()
    except Exception as e:
        return _error_payload(query, caller, 'DB_UNREACHABLE', str(e))

    # Build payload
    payload = {
        'query': query,
        'caller': caller,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'latency': {
            'embed_ms': round(t_embed * 1000),
            'pg_query_ms': round(t_pg * 1000),
            'total_ms': round((time.time() - t0) * 1000),
        },
        'results': [],
        'advisory_notes': [],
        'next_action': 'ADVISORY_ONLY',
    }

    for (path, ci, content, sim, doc_status, domain, tier, layer) in results:
        payload['results'].append({
            'source_path': path,
            'chunk_index': ci,
            'similarity': round(sim, 4),
            'content_preview': content[:200].replace('\n', ' '),
            'metadata': {
                'doc_status': doc_status,
                'domain': domain,
                'tier': tier,
                'prompt_knowledge_layer': layer,
            }
        })

    return payload

def _error_payload(query, caller, error_type, detail):
    return {
        'query': query,
        'caller': caller,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'results': [],
        'advisory_notes': [{'type': error_type, 'detail': detail[:200]}],
        'next_action': 'ADVISORY_ONLY',
    }

def collect_stats():
    """
    索引规模统计：连接 harness_rag 库，统计 chunk 总数、
    去重 source_path 数，以及按 domain/tier/doc_status 的分布。
    不需要 embedding API。返回 dict；连接失败返回
    {'error': 'DB_UNREACHABLE', 'detail': ...}，由调用方转非零退出码。
    """
    try:
        conn = get_pg_conn()
        cur = conn.cursor()

        cur.execute(f'''
            SELECT COUNT(*), COUNT(DISTINCT source_path)
            FROM {DB_CFG['table']};
        ''')
        total_chunks, distinct_sources = cur.fetchone()

        def group_by(column):
            cur.execute(f'''
                SELECT {column}, COUNT(*)
                FROM {DB_CFG['table']}
                GROUP BY {column}
                ORDER BY COUNT(*) DESC, {column};
            ''')
            return {(key if key is not None else '(null)'): cnt for key, cnt in cur.fetchall()}

        by_domain = group_by('domain')
        by_tier = group_by('tier')
        by_doc_status = group_by('doc_status')

        conn.close()
    except Exception as e:
        return {'error': 'DB_UNREACHABLE', 'detail': str(e)}

    return {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'database': DB_CFG['dbname'],
        'table': DB_CFG['table'],
        'total_chunks': total_chunks,
        'distinct_source_paths': distinct_sources,
        'by_domain': by_domain,
        'by_tier': by_tier,
        'by_doc_status': by_doc_status,
    }

# ── CLI ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='M14 RAG Search')
    parser.add_argument('query', nargs='?', default=None, help='Search query text')
    parser.add_argument('--caller', default='manual', help='Caller ID (W1/M1/W9/W7/P1)')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--stats', action='store_true',
                        help='Print index statistics (total chunks, distinct sources, domain/tier/doc_status distribution); no query needed')
    parser.add_argument('--top-k', type=int, default=5, help='Number of results')
    parser.add_argument('--filter-domain', nargs='*', default=[], help='Filter by domain')
    parser.add_argument('--filter-tier', nargs='*', default=[], help='Filter by tier')
    parser.add_argument('--filter-layer', nargs='*', default=[], help='Filter by knowledge layer')
    args = parser.parse_args()

    if args.stats:
        if args.query is not None:
            parser.error('--stats is mutually exclusive with query')
        stats = collect_stats()
        if 'error' in stats:
            detail = stats['detail'][:500]
            if args.json:
                print(json.dumps({'error': stats['error'], 'detail': detail}, ensure_ascii=False, indent=2))
            else:
                print(f"ERROR: {stats['error']}: {detail}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps(stats, ensure_ascii=False, indent=2))
        else:
            print(f"M14 RAG Index Stats (db={stats['database']}, table={stats['table']})")
            print('-' * 60)
            print(f"  Total chunks        : {stats['total_chunks']}")
            print(f"  Distinct sources    : {stats['distinct_source_paths']}")
            print(f"\n  By domain:")
            for k, v in stats['by_domain'].items():
                print(f"    {k:<28} {v}")
            print(f"\n  By tier:")
            for k, v in stats['by_tier'].items():
                print(f"    {k:<28} {v}")
            print(f"\n  By doc_status:")
            for k, v in stats['by_doc_status'].items():
                print(f"    {k:<28} {v}")
        return

    if args.query is None:
        parser.error('query is required unless --stats is used')

    filters = {}
    if args.filter_domain:
        filters['domain_include'] = args.filter_domain
    if args.filter_tier:
        filters['tier_include'] = args.filter_tier
    if args.filter_layer:
        filters['layer_include'] = args.filter_layer

    payload = search(args.query, caller=args.caller, top_k=args.top_k, filters=filters)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f'M14 RAG Search: "{args.query}" (caller={args.caller})')
        print('-' * 60)
        if payload.get('advisory_notes'):
            for note in payload['advisory_notes']:
                print(f'  ⚠️  {note["type"]}: {note.get("detail", "")}')
        for i, r in enumerate(payload['results']):
            short = r['source_path'].replace('@@USERPROFILE:escaped@@\\', '~\\')
            print(f'\n  [{i+1}] sim={r["similarity"]:.4f} | {short}')
            print(f'      {r["content_preview"][:100]}...')
            print(f'      [{r["metadata"]["doc_status"]}] [{r["metadata"]["domain"]}] [{r["metadata"]["tier"]}] [{r["metadata"]["prompt_knowledge_layer"]}]')
        lat = payload.get('latency', {})
        print(f'\n  Latency: embed={lat.get("embed_ms",0)}ms pg={lat.get("pg_query_ms",0)}ms total={lat.get("total_ms",0)}ms')

if __name__ == '__main__':
    main()
