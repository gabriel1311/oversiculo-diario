// Renderiza um episódio: node serie/render.js serie/quarenta [--previa 1,10,30]
// Monta a linha do tempo pelas durações da narração (tempos.json), desenha cada
// quadro no Chrome (motor.html), passa os quadros ao ffmpeg e mistura voz + trilha.
const fs = require('fs'), path = require('path'), { spawn, execFileSync } = require('child_process');
const puppeteer = require('puppeteer-core');

const pasta = path.resolve(process.argv[2]);
const iPrev = process.argv.indexOf('--previa');
const previa = iPrev > 0 ? process.argv[iPrev + 1].split(',').map(Number) : null;
const FPS = 30, ATRASO_FALA = 0.35;
const roteiro = JSON.parse(fs.readFileSync(path.join(pasta, 'roteiro.json')));
const tempos = JSON.parse(fs.readFileSync(path.join(pasta, 'tempos.json')));

let ini = 0;
const linha = roteiro.cenas.map(c => {
  const fala = tempos[c.id] || 0;
  const folga = c.id === 'gancho' ? 0.7 : c.id === 'fecho' ? 2.2 : 1.2;
  const dur = c.id === 'assinatura' ? 4.5 : fala + ATRASO_FALA + folga;
  const cena = { ...c, ini, dur, fala };
  ini += dur;
  return cena;
});
const TOTAL = ini;
fs.writeFileSync(path.join(pasta, 'linha.json'), JSON.stringify(linha.map(({ id, ini, dur }) => ({ id, ini: +ini.toFixed(2), dur: +dur.toFixed(2) })), null, 1));

(async () => {
  // Abre o Chrome sem janela com perfil próprio (nunca o Chrome do Gabriel) e conecta.
  const perfil = process.env.CHROME_PERFIL || path.join(require('os').tmpdir(), 'serie-chrome');
  const chrome = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', ['--headless=new', '--remote-debugging-port=0',
    '--allow-file-access-from-files', '--no-first-run', '--hide-scrollbars', `--user-data-dir=${perfil}`, 'about:blank'], { stdio: ['ignore', 'ignore', 'pipe'] });
  const ws = await new Promise((ok, falha) => {
    let buf = ''; const lim = setTimeout(() => falha(new Error('Chrome não respondeu')), 60000);
    chrome.stderr.on('data', d => { buf += d; const m = buf.match(/ws:\/\/\S+/); if (m) { clearTimeout(lim); ok(m[0]); } });
  });
  const nav = await puppeteer.connect({ browserWSEndpoint: ws, defaultViewport: null });
  const fechar = nav.close.bind(nav);
  nav.close = async () => { await fechar().catch(() => {}); chrome.kill(); };
  const pg = await nav.newPage();
  await pg.setViewport({ width: 1080, height: 1920 });
  await pg.goto('file://' + path.resolve(__dirname, 'motor.html'));
  await pg.evaluate(async l => { window.LINHA = l; await window.pronto; }, linha);
  const quadro = async t => {
    const b64 = await pg.evaluate(t => { window.renderizar(t); return document.getElementById('c').toDataURL('image/jpeg', 0.93).split(',')[1]; }, t);
    return Buffer.from(b64, 'base64');
  };

  if (previa) {
    fs.mkdirSync(path.join(pasta, 'previa'), { recursive: true });
    for (const t of previa) fs.writeFileSync(path.join(pasta, 'previa', `t${String(t).padStart(5, '0')}.jpg`), await quadro(t));
    await nav.close(); console.log('prévias ok, total', TOTAL.toFixed(1), 's'); return;
  }

  const mudo = path.join(pasta, 'video-mudo.mp4');
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-',
    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-preset', 'medium', '-crf', '19', '-r', String(FPS), mudo], { stdio: ['pipe', 'inherit', 'inherit'] });
  const n = Math.ceil(TOTAL * FPS);
  const t0 = Date.now();
  for (let i = 0; i < n; i++) {
    const buf = await quadro(i / FPS);
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if (i % 300 === 0) console.log(`quadro ${i}/${n} (${((Date.now() - t0) / 1000).toFixed(0)} s)`);
  }
  ff.stdin.end();
  await new Promise(r => ff.on('close', r));
  await nav.close();

  // Áudio: cada fala no início da sua cena + trilha baixinha com fade.
  const falas = linha.filter(c => c.fala > 0);
  const args = ['-y', '-loglevel', 'error', '-i', mudo];
  falas.forEach(c => args.push('-i', path.join(pasta, 'audio', `${c.id}.mp3`)));
  const trilha = path.resolve(__dirname, '..', 'audio', roteiro.trilha || 'cinematic-leberch.mp3');
  args.push('-stream_loop', '-1', '-i', trilha);
  const filtros = falas.map((c, i) => { const ms = Math.round((c.ini + ATRASO_FALA) * 1000); return `[${i + 1}:a]adelay=${ms}|${ms},volume=1.0[f${i}]`; });
  const it = falas.length + 1;
  filtros.push(`[${it}:a]atrim=0:${TOTAL.toFixed(2)},volume=0.13,afade=t=in:d=1.5,afade=t=out:st=${(TOTAL - 3).toFixed(2)}:d=3[m]`);
  filtros.push(`${falas.map((_, i) => `[f${i}]`).join('')}[m]amix=inputs=${falas.length + 1}:normalize=0:duration=longest,atrim=0:${TOTAL.toFixed(2)},loudnorm=I=-15:TP=-1.5[a]`);
  args.push('-filter_complex', filtros.join(';'), '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', path.join(pasta, 'episodio.mp4'));
  execFileSync('ffmpeg', args, { stdio: 'inherit' });
  console.log('episódio pronto:', path.join(pasta, 'episodio.mp4'), TOTAL.toFixed(1), 's');
})();
