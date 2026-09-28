import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve('..');
const escape = s => s.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
const files = ['SYSTEM-GUIDE-TH.md', 'ARCHITECTURE.md', 'RUNBOOK.md', 'VALIDATION.md', 'LEARNING-ROADMAP.md'];
const sections = files.map(name => {
  const text = fs.readFileSync(path.join(root, 'docs', name), 'utf8');
  let inCode = false;
  return '<section>' + text.split('\n').map(line => {
    if (line.startsWith('```')) { inCode = !inCode; return inCode ? '<pre>' : '</pre>'; }
    if (inCode) return escape(line) + '\n';
    const match = line.match(/^(#{1,3}) (.*)$/);
    if (match) return `<h${match[1].length}>${escape(match[2])}</h${match[1].length}>`;
    return line.trim() ? `<p>${escape(line)}</p>` : '';
  }).join('') + '</section>';
}).join('');
const font = fs.readFileSync(path.join(root, 'docs/assets/Sarabun-Regular.ttf')).toString('base64');
const bold = fs.readFileSync(path.join(root, 'docs/assets/Sarabun-Bold.ttf')).toString('base64');
const browser = await chromium.launch({channel:'chrome', headless:true});
const page = await browser.newPage();
await page.setContent(`<html lang="th"><meta charset="utf-8"><style>
@font-face{font-family:Sarabun;src:url(data:font/ttf;base64,${font})}
@font-face{font-family:Sarabun;font-weight:700;src:url(data:font/ttf;base64,${bold})}
body{font:11pt/1.65 Sarabun,sans-serif;color:#192827}h1{font-size:23pt;color:#154a40}h2{font-size:16pt;margin-top:24pt}h3{font-size:12pt}h1,h2,h3{break-after:avoid}p{margin:7pt 0;overflow-wrap:anywhere}pre{font:9pt/1.5 monospace;white-space:pre-wrap;overflow-wrap:anywhere;padding:10pt;background:#f0f4f2}section+section{break-before:page}
</style><body>${sections}</body></html>`);
await page.evaluate(() => document.fonts.ready);
await page.pdf({path:path.join(root,'docs/VeriForge-System-Guide-TH.pdf'),format:'A4',printBackground:true,margin:{top:'18mm',bottom:'20mm',left:'18mm',right:'18mm'},displayHeaderFooter:true,headerTemplate:'<span></span>',footerTemplate:'<div style="font-size:8px;width:100%;text-align:center">VeriForge local v1 · <span class="pageNumber"></span> / <span class="totalPages"></span></div>'});
await browser.close();
console.log('System guide PDF exported from current project documents.');
