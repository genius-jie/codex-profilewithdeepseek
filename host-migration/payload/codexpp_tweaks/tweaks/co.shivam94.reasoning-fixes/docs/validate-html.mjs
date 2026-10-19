#!/usr/bin/env node
import { readFileSync } from 'node:fs';

const path = process.argv[2];
if (!path) { console.error('Usage: node validate-html.mjs <file.html>'); process.exit(1); }

const html = readFileSync(path, 'utf-8');
let errors = 0;
let warnings = 0;
let pad = s => String(s).padStart(3);

function fail(type, msg) {
  const icon = type === 'ERR' ? '✖' : '⚠';
  console.log(`  ${icon}  [${type}] ${msg}`);
  type === 'ERR' ? errors++ : warnings++;
}

console.log(`\nValidating ${path}...\n`);

// ── 1. SVG text with HTML tags ──
// Use simple index-based search to avoid regex backtracking
let idx = 0;
let svgTextCount = 0;
while (idx < html.length) {
  const textStart = html.indexOf('<text', idx);
  if (textStart === -1) break;
  const contentStart = html.indexOf('>', textStart) + 1;
  const textEnd = html.indexOf('</text>', contentStart);
  if (textEnd === -1) { idx = textStart + 1; continue; }
  const raw = html.slice(contentStart, textEnd);
  svgTextCount++;
  // Check for HTML tags inside (but allow <tspan> and <animate> as SVG children)
  const stripped = raw.replace(/<tspan[^>]*>/g, '').replace(/<\/tspan>/g, '');
  if (/<[a-z]+[ >]/.test(stripped)) {
    const sample = stripped.trim().slice(0, 80).replace(/\s+/g, ' ');
    fail('ERR', `SVG <text> contains HTML tag: "${sample}..."`);
  }
  idx = textEnd + 7;
}
if (svgTextCount === 0) fail('WARN', 'No SVG <text> elements found (diagrams may be missing)');

// ── 2. Annotation overlapping arrows ──
// Collect all y coords from sub labels and arrow lines
const labelY = [];
const labelRe = /class="sub"[^>]*y="(\d+)"/g;
let m;
while ((m = labelRe.exec(html)) !== null) labelY.push(+m[1]);

const arrowY1 = [];
const arrowRe = /class="arrow"[^>]*y1="(\d+)"/g;
while ((m = arrowRe.exec(html)) !== null) arrowY1.push(+m[1]);

const arrowY2 = [];
const arrowRe2 = /class="arrow"[^>]*y2="(\d+)"/g;
while ((m = arrowRe2.exec(html)) !== null) arrowY2.push(+m[1]);

for (const ly of labelY) {
  for (const ay of [...arrowY1, ...arrowY2]) {
    if (Math.abs(ly - ay) < 6) {
      fail('WARN', `Annotation at y=${ly} near arrow at y=${ay} (within 6px)`);
    }
  }
}

// ── 3. Dark mode specificity ──
if (html.includes('prefers-color-scheme: dark')) {
  if (/\.dark-mode\s*\{/.test(html) && !html.includes('html[data-dm=') && !/html\.dark-mode/.test(html)) {
    fail('WARN', 'Uses .dark-mode class without html[data-dm] specificity — may be overridden by @media :root');
  }
}

// ── 4. Matching SVG/Details tags ──
const countTag = (tag, open) => {
  const pattern = open ? `<${tag}[\\s>]` : `<\\/${tag}>`;
  const re = new RegExp(pattern, 'g');
  let c = 0;
  while (re.exec(html) !== null) c++;
  return c;
};
const svgOpens = countTag('svg', true);
const svgCloses = countTag('svg', false);
if (svgOpens !== svgCloses) fail('ERR', `SVG: ${pad(svgOpens)} opens, ${pad(svgCloses)} closes`);

const detOpens = countTag('details', true);
const detCloses = countTag('details', false);
if (detOpens !== detCloses) fail('ERR', `<details>: ${pad(detOpens)} opens, ${pad(detCloses)} closes`);

// ── 5. JS onclick references exist ──
const onclickFns = new Set();
const onclickRe = /onclick="(\w+)\(/g;
while ((m = onclickRe.exec(html)) !== null) onclickFns.add(m[1]);
for (const fn of onclickFns) {
  const fnRe = new RegExp(`function ${fn}\\(`, 'g');
  if (!fnRe.test(html)) {
    fail('ERR', `onclick="${fn}()" but no function ${fn} defined`);
  }
}

// ── 6. ViewBox vs content bounds ──
const vbMatch = html.match(/viewBox="0 0 \d+ (\d+)"/);
if (vbMatch) {
  const vbHeight = +vbMatch[1];
  let maxY = 0;
  const allY = /y="(\d+)"/g;
  while ((m = allY.exec(html)) !== null) {
    const y = +m[1];
    if (y > maxY) maxY = y;
  }
  if (maxY > vbHeight - 20) {
    fail('WARN', `SVG viewBox height=${vbHeight} but content reaches y=${maxY} (${maxY - vbHeight + 20}px may clip)`);
  }
}

// ── 7. body transition for dark mode ──
if (html.includes('dmToggle') && !html.includes('transition: background')) {
  fail('WARN', 'Dark mode toggle present but body missing transition for smooth color switch');
}

// ── 8. <td> outside <table> (grid vs table-cell mismatch) ──
// <td> inside a CSS Grid container causes broken layouts — use <div> instead
let tdCount = 0;
let tdInTable = 0;
let tdIdx = 0;
while (tdIdx < html.length) {
  const tdStart = html.indexOf('<td', tdIdx);
  if (tdStart === -1) break;
  tdCount++;
  // Check if this <td> is inside a <table> by scanning backwards
  const beforeTd = html.slice(Math.max(0, tdStart - 500), tdStart);
  const lastTable = beforeTd.lastIndexOf('<table');
  const lastTableClose = beforeTd.lastIndexOf('</table>');
  if (lastTable > lastTableClose) tdInTable++;
  tdIdx = tdStart + 1;
}
const tdOutside = tdCount - tdInTable;
if (tdOutside > 0) {
  fail('ERR', `${tdOutside} <td> outside <table> — use <div> for CSS Grid children, not table-cell elements`);
  // Show first few locations
  let locIdx = 0;
  let found = 0;
  while (found < 3 && locIdx < html.length) {
    const s = html.indexOf('<td', locIdx);
    if (s === -1) break;
    // Check if inside a table
    const before = html.slice(Math.max(0, s - 500), s);
    if (before.lastIndexOf('<table') <= before.lastIndexOf('</table>')) {
      const lineNum = (html.slice(0, s).match(/\n/g) || []).length + 1;
      const context = html.slice(Math.max(0, s - 40), s + 40).replace(/\n/g, ' ');
      fail('INFO', `  -> line ${lineNum}: ...${context.trim()}...`);
      found++;
    }
    locIdx = s + 1;
  }
}
console.log(`\n  ${errors + warnings} issues (${errors} errors, ${warnings} warnings)`);
process.exit(errors > 0 ? 1 : 0);
