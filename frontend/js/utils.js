export const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const size = n => n < 1048576 ? `${Math.ceil(n/1024)} KB` : `${(n/1048576).toFixed(1)} MB`;
export function download(name, content, type) {
  const url = URL.createObjectURL(new Blob([content], {type}));
  const link = document.createElement('a'); link.href = url; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function asText(value, indent = '') {
  if (value === null || value === undefined) return '';
  if (Array.isArray(value)) return value.map((v,i) => `${indent}${i+1}. ${asText(v, indent+'  ')}`).join('\n\n');
  if (typeof value === 'object') return Object.entries(value).map(([k,v]) => `${indent}${k.replaceAll('_',' ').toUpperCase()}\n${asText(v, indent+'  ')}`).join('\n\n');
  return indent + String(value);
}
export function cardImage(title, text) {
  const canvas = document.createElement('canvas'); const ctx = canvas.getContext('2d');
  const wrap = (str, font) => {
    ctx.font = font; const lines = [];
    for (const para of str.split('\n')) {
      let line = '';
      for (const word of para.split(' ')) {
        if (ctx.measureText(line+word).width > 940 && line) { lines.push(line); line=''; }
        line += word+' ';
      }
      lines.push(line);
    }
    return lines;
  };
  canvas.width=1080;
  const heading=wrap(title,'bold 36px sans-serif'), lines=wrap(text,'28px sans-serif');
  canvas.height=Math.max(640,180+heading.length*48+lines.length*42);
  ctx.fillStyle='#f7f9f6'; ctx.fillRect(0,0,canvas.width,canvas.height);
  ctx.fillStyle='#287b55'; ctx.font='bold 20px sans-serif'; ctx.fillText('REVIEWARUDO / STUDY SMARTER',70,65);
  let y=140; ctx.fillStyle='#183b2a'; ctx.font='bold 36px sans-serif';
  heading.forEach(line=>{ctx.fillText(line,70,y);y+=48;}); y+=30; ctx.font='28px sans-serif';
  lines.forEach(line=>{ctx.fillText(line,70,y);y+=42;});
  canvas.toBlob(blob=>download('reviewarudo-card.png',blob,'image/png'));
}
