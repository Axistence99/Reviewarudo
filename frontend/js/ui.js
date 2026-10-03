import {escapeHTML as e, asText} from './utils.js';
export const $ = id => document.getElementById(id);
export const icons = () => window.lucide?.createIcons();
export function notify(message) { $('notification').textContent=message; $('notification').hidden=!message; if(message) $('notification').scrollIntoView({behavior:'smooth',block:'nearest'}); }
export function source(ref) {
  if(!ref) return '';
  const type = ref.file?.toLowerCase().endsWith('.pptx')?'Slide':ref.file?.toLowerCase().endsWith('.docx')?'Section':'Page';
  return `<p class="source">Source: ${e(ref.file)} — ${type} ${e(ref.page)}</p>`;
}
export function list(values) { return `<ul>${(values||[]).map(x=>`<li>${e(x)}</li>`).join('')}</ul>`; }
export function heading(title, subtitle, icon='book-open') { return `<div class="study-header"><div><div class="eyebrow">YOUR LEARNING SPACE</div><h1>${e(title)}</h1><p>${e(subtitle)}</p></div><span class="badge"><i data-lucide="${icon}"></i></span></div>`; }
export function empty(title) { return `<div class="empty"><i data-lucide="book-open"></i><h2>No ${e(title)} yet.</h2><p>Upload your study materials to generate one, or explore the demo.</p><button class="button primary" data-go-upload>Create study materials</button></div>`; }
export function reviewer(material) {
  const summary=material.summary;
  return heading(material.title,`${material.source_files.join(' · ')} · Check source references as you study.`) + `<div class="study-body">${material.warnings.length?`<div class="panel">${list(material.warnings)}</div>`:''}${summary?`<section class="panel"><span class="eyebrow">THE BIG PICTURE</span><h2>Overview</h2><p>${e(summary.overview)}</p><h3>Section summaries</h3>${list(summary.section_summaries)}<h3>Key takeaways</h3>${list(summary.key_takeaways)}<p>${e(summary.final_review)}</p>${source(summary.source_reference)}</section>`:''}${material.topics.length?`<div class="reading-progress"><small id="read-count">0 of ${material.topics.length} topics marked read</small><progress id="read-progress" value="0" max="${material.topics.length}"></progress></div>`:''}${material.topics.map((t,i)=>`<details open class="panel"><summary>${i+1}. ${e(t.title)}</summary><p>${e(t.summary)}</p>${list(t.key_points)}${t.key_terms.length?`<h3>Important terms</h3>${t.key_terms.map(k=>`<p><strong>${e(k.term)}</strong> — ${e(k.definition)}</p>${source(k.source_reference)}`).join('')}`:''}${t.examples.length?`<h3>Examples</h3>${list(t.examples)}`:''}${t.relationships.length?`<h3>Connections</h3>${list(t.relationships)}`:''}${source(t.source_reference)}<div class="toolbar"><label><input type="checkbox" data-read="${i}"> Mark as read</label><button class="button secondary small" data-section-image="${i}">Save section image</button></div></details>`).join('')}${!summary&&!material.topics.length?empty('reviewer (not selected)'):''}</div>`;
}
export function glossary(material) {
  const terms=material.key_terms.length?material.key_terms:material.topics.flatMap(t=>t.key_terms);
  return heading('A little clarity goes a long way.','The essential terms, all in one place.','whole-word')+(terms.length?`<div class="terms">${terms.map(k=>`<article class="panel"><h3>${e(k.term)}</h3><p>${e(k.definition)}</p>${source(k.source_reference)}</article>`).join('')}</div>`:empty('glossary'));
}
export function guide(material) {
  const g=material.study_guide;
  return heading('Your roadmap to understanding.','Work through the concepts, then check what you know.','route')+(g?`<div class="study-body">${Object.entries(g).filter(([k])=>k!=='source_reference').map(([k,v])=>`<section class="panel"><h2>${e(k.replaceAll('_',' ').replace(/^./,c=>c.toUpperCase()))}</h2>${Array.isArray(v)?list(v):`<p>${e(v)}</p>`}</section>`).join('')}${source(g.source_reference)}</div>`:empty('study guide'));
}
export function printMaterial(material) {
  const groups=[['Summary',material.summary],['Reviewer',material.topics],['Key terms',material.key_terms],['Study guide',material.study_guide],['Flashcards',material.flashcards],['Quiz questions',material.quiz.map(({question,choices,source_reference})=>({question,choices,source_reference}))],['Identification questions',material.identification.map(({question})=>({question}))],['True or false',material.true_false.map(({statement})=>({statement}))],['Fill in the blank',material.fill_in_the_blank.map(({question})=>({question}))],['Answer key',{quiz:material.quiz.map(({correct_answer,explanation})=>({correct_answer,explanation})),identification:material.identification,true_false:material.true_false,fill_in_the_blank:material.fill_in_the_blank}],['Notes',material.warnings]];
  $('print-content').innerHTML=`<h1>${e(material.title)}</h1><p>Sources: ${e(material.source_files.join(', '))}</p>${groups.filter(([,v])=>v && (!Array.isArray(v)||v.length)).map(([label,value])=>`<section><h2>${label}</h2><pre>${e(asText(value))}</pre></section>`).join('')}`;
  window.print();
}
