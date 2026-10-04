import {
  request
} from './api.js';
import {
  escapeHTML as e,
  size,
  download,
  asText,
  cardImage
} from './utils.js';
import {
  $,
  icons,
  notify,
  source,
  heading,
  empty,
  reviewer,
  glossary,
  guide,
  printMaterial,
  revealNotice
} from './ui.js';
const MATERIAL_OPTIONS = [
  ['reviewer', 'book-open', 'Comprehensive reviewer', 'The full picture'],
  ['flashcards', 'gallery-vertical-end', 'Flashcards', 'Recall. Flip. Remember.'],
  ['quiz', 'list-checks', 'Multiple choice', 'Put knowledge to the test'],
  ['summary', 'align-left', 'Summary', 'The essentials, distilled'],
  ['key_terms', 'whole-word', 'Key terms', 'Build your vocabulary'],
  ['study_guide', 'route', 'Study guide', 'A clear path to learning'],
  ['identification', 'search', 'Identification', 'Name that concept'],
  ['true_false', 'circle-check', 'True or false', 'Check your understanding'],
  ['fill_in_the_blank', 'text-cursor-input', 'Fill in the blank', 'Connect the missing pieces']
];
// Uploaded binaries/text stay in memory; only the generated set is saved per tab.
let files = [],
  documents = [],
  material = null,
  busy = false,
  currentView = 'upload';
// Study progress is deliberately temporary and resets with a new generated set.
let cardOrder = [],
  cardIndex = 0,
  known = new Set(),
  again = new Set();
let mode = 'quiz',
  questionIndex = 0,
  answers = [],
  selected = null,
  submitted = false;
let readTopics = new Set();
const VIEW_LABELS = {
  library: 'My library',
  progress: 'Study progress',
  upload: 'Create reviewer',
  reviewer: 'My reviewer',
  flashcards: 'Flashcards',
  quiz: 'Practice quiz',
  key_terms: 'Key terms',
  study_guide: 'Study guide',
  export: 'Export materials'
};
$('material-types').innerHTML = MATERIAL_OPTIONS.map(([value, icon, title, desc], i) =>
  `<label class="material-option"><input type="checkbox" name="material" value="${value}" ${i<3?'checked':''}><i data-lucide="${icon}"></i><strong>${title}</strong><small>${desc}</small></label>`
  ).join('');
const selectedTypes = () => [...document.querySelectorAll('input[name=material]:checked')].map(x =>
  x.value);
$('material-types').addEventListener('change', () => {
  $('selected-count').textContent = `${selectedTypes().length} materials selected`;
  updateStudySet();
});
$('counts').addEventListener('click', event => {
  const b = event.target.closest('[data-count]');
  if (!b) return;
  $('question-count').value = b.dataset.count;
  for (const x of $('counts').children) {
    x.classList.toggle('selected', x === b);
    x.setAttribute('aria-pressed', x === b);
  }
});
$('language').addEventListener('change', () => {
  $('custom-language').hidden = $('language').value !== 'Other';
});

function saveStudySession() {
  try {
    sessionStorage.setItem('reviewarudo-material', JSON.stringify(material));
  } catch {
    notify(
      'Your material is ready, but browser storage is unavailable or full. Export it before closing this tab.'
      );
  }
}

function resetStudyProgress() {
  cardOrder = material.flashcards.map((_, i) => i);
  cardIndex = 0;
  known = new Set();
  again = new Set();
  readTopics = new Set();
  resetQuizProgress();
}

function resetQuizProgress() {
  questionIndex = 0;
  answers = [];
  selected = null;
  submitted = false;
}

function setMaterial(data) {
  material = data;
  resetStudyProgress();
  saveStudySession();
  $('step-study').classList.add('active');
  showView('reviewer');
}
try {
  const stored = sessionStorage.getItem('reviewarudo-material');
  if (stored) {
    material = JSON.parse(stored);
    if (!Array.isArray(material.flashcards) || !Array.isArray(material.topics)) material = null;
    else resetStudyProgress();
  }
} catch {
  material = null;
}

function showView(view) {
  if (busy) return;
  currentView = view;
  for (const name of Object.keys(VIEW_LABELS)) $(`view-${name}`).hidden = name !== view;
  document.querySelectorAll('[data-view]').forEach(b => {
    b.classList.toggle('active', b.dataset.view === view);
    b.setAttribute('aria-current', b.dataset.view === view ? 'page' : 'false');
  });
  $('crumb').textContent = VIEW_LABELS[view];
  $('material-downloads').hidden = !material || ['upload', 'export', 'library', 'progress']
    .includes(view);
  $('study-tools').hidden = !material;
  document.querySelector('[data-create]').classList.toggle('active', view === 'upload');
  document.querySelector('[data-create]').setAttribute('aria-current', view === 'upload' ? 'page' :
    'false');
  if (view !== 'upload') renderCurrentView();
  icons();
  // View changes do not navigate the browser, so reset the previous view's scroll.
  window.scrollTo({
    top: 0,
    behavior: 'instant'
  });
  $('main').focus({
    preventScroll: true
  });
}
$('navigation').addEventListener('click', event => {
  const button = event.target.closest('button');
  if (!button || busy) return;
  const view = button.hasAttribute('data-create') ? 'upload' : button.hasAttribute(
    'data-library') ? 'library' : button.dataset.view;
  if (!view) return;
  showView(view);
  if (view === 'upload') $('browse').focus({
    preventScroll: true
  });
});

function updateStudySet() {
  $('set-status').textContent = files.length ?
    `${files.length} ${files.length === 1 ? 'material' : 'materials'}, endless possibilities` :
    'Ready when you are';
  $('set-files').innerHTML = files.length ? files.map(file =>
    `<div class="set-file"><i data-lucide="file-text"></i><span title="${e(file.name)}">${e(file.name)}</span><i data-lucide="check"></i></div>`
    ).join('') : '<p>Your materials will appear here.</p>';
  $('set-types').innerHTML = selectedTypes().map(type =>
      `<span>${e(MATERIAL_OPTIONS.find(t => t[0] === type)[2])}</span>`).join('') ||
    '<p>Select at least one study format.</p>';
  icons();
}

function libraryView() {
  const resources = MATERIAL_OPTIONS.filter(([key]) => key === 'reviewer' ? material.topics.length :
    Array.isArray(material[key]) ? material[key].length : material[key]);
  return heading('Your learning universe.', 'One study set. Every way to make it yours.',
    'library') +
    `<div class="session-banner"><i data-lucide="layers"></i><div><strong>${e(material.title)}</strong><p>Current browser session · ${material.source_files.length} source files · Export a copy before clearing this session.</p></div></div><div class="library-grid">${resources.map(([key,icon,title,desc]) => `<article class="panel resource-card"><i data-lucide="${icon}"></i><h2>${e(title)}</h2><p>${e(desc)}</p><button class="button secondary" data-resource="${key}">Open material <i data-lucide="arrow-up-right"></i></button></article>`).join('')}</div>`;
}

function progressView() {
  const correct = answers.filter(Boolean).length;
  return heading('Small steps. Real progress.',
      'Your activity in this open session. Progress resets when you reload or start a new set.',
      'orbit') +
    `<div class="progress-grid"><section class="panel progress-card"><h2>Reviewer topics read</h2><strong>${readTopics.size} / ${material.topics.length}</strong><progress aria-label="Reviewer topics read" value="${readTopics.size}" max="${material.topics.length || 1}"></progress><p>Mark topics as read in your reviewer.</p></section><section class="panel progress-card"><h2>Flashcards known</h2><strong>${known.size} / ${material.flashcards.length}</strong><progress aria-label="Flashcards known" value="${known.size}" max="${material.flashcards.length || 1}"></progress><p>${again.size} cards marked for another review.</p></section><section class="panel progress-card"><h2>Current practice score</h2><strong>${correct} / ${answers.length}</strong><progress aria-label="Correct practice answers" value="${correct}" max="${answers.length || 1}"></progress><p>${e(mode.replaceAll('_',' '))} · ${answers.length} submitted answers.</p></section></div>`;
}

function renderCurrentView() {
  const container = $('view-' + currentView);
  if (!material) {
    container.innerHTML = empty(VIEW_LABELS[currentView].toLowerCase());
    icons();
    return;
  }
  if (currentView === 'library') container.innerHTML = libraryView();
  if (currentView === 'progress') container.innerHTML = progressView();
  if (currentView === 'reviewer') {
    container.innerHTML = reviewer(material);
    container.querySelectorAll('[data-read]').forEach(c => c.checked = readTopics.has(Number(c
      .dataset.read)));
    updateReadingProgress();
  }
  if (currentView === 'key_terms') container.innerHTML = glossary(material);
  if (currentView === 'study_guide') container.innerHTML = guide(material);
  if (currentView === 'flashcards') renderCards();
  if (currentView === 'quiz') renderQuiz();
  if (currentView === 'export') container.innerHTML = heading('Take your learning with you.',
      'Save a copy, print a reviewer, or keep a backup.', 'download') +
    `<div class="export-grid"><section class="panel"><i data-lucide="file-text"></i><h2>Print-ready PDF</h2><p>All study materials with a separate quiz answer key. Choose “Save as PDF” in your browser’s print dialog.</p><button class="button primary" data-export="print">Print / Save as PDF</button></section><section class="panel"><i data-lucide="file-json"></i><h2>Structured JSON</h2><p>Your complete generated resources, including source references, in a portable data format.</p><button class="button secondary" data-export="json">Download JSON</button></section><section class="panel"><i data-lucide="notebook-text"></i><h2>Plain text</h2><p>A clean, readable copy of all your resources. Bring it into your favorite note-taking app.</p><button class="button secondary" data-export="text">Download text</button></section></div><p class="help">Individual flashcards and reviewer topics can also be saved as PNG images from their study views.</p>`;
  icons();
}

function renderFileList() {
  $('files').innerHTML = files.map((file, i) =>
    `<div class="file-card"><i data-lucide="file-text"></i><div><strong>${e(file.name)}</strong><small>${e(file.name.split('.').pop().toUpperCase())} · ${size(file.size)}</small></div><span class="file-status">${documents.length?'✓ Extracted':'Ready'}</span><button aria-label="Remove ${e(file.name)}" data-remove="${i}" ${busy?'disabled':''}><i data-lucide="x"></i></button></div>`
    ).join('');
  $('extract').disabled = !files.length || busy;
  updateStudySet();
  icons();
}

function invalidateExtraction() {
  documents = [];
  $('preview-panel').hidden = true;
  $('step-config').classList.remove('active');
  renderFileList();
}

function addSelectedFiles(incoming) {
  if (busy) return;
  notify('');
  const errors = [];
  for (const file of incoming) {
    if (!/\.(pdf|docx|pptx)$/i.test(file.name)) {
      errors.push(
        `${file.name}: This file type is not supported. Please upload PDF, DOCX, or PPTX.`);
      continue;
    }
    if (file.size > 10 * 1024 * 1024) {
      errors.push(`${file.name}: exceeds 10 MB.`);
      continue;
    }
    if (files.length >= 8 || files.reduce((a, f) => a + f.size, 0) + file.size > 30 * 1024 * 1024) {
      errors.push('Upload up to 8 files and 30 MB total.');
      continue;
    }
    if (files.some(f => f.name === file.name)) {
      errors.push(
        `${file.name}: a file with this name is already selected. Rename it if it is a different document.`
        );
      continue;
    }
    files.push(file);
  }
  invalidateExtraction();
  if (errors.length) notify(errors.join(' '));
}
$('browse').onclick = () => $('file-input').click();
$('file-input').onchange = event => {
  addSelectedFiles(event.target.files);
  event.target.value = '';
};
$('files').onclick = event => {
  const b = event.target.closest('[data-remove]');
  if (b && !busy) {
    files.splice(Number(b.dataset.remove), 1);
    invalidateExtraction();
  }
};
for (const name of ['dragenter', 'dragover']) $('dropzone').addEventListener(name, event => {
  event.preventDefault();
  $('dropzone').classList.add('dragging');
});
for (const name of ['dragleave', 'drop']) $('dropzone').addEventListener(name, event => {
  event.preventDefault();
  $('dropzone').classList.remove('dragging');
});
$('dropzone').addEventListener('drop', event => addSelectedFiles(event.dataTransfer.files));
let timer;

function setProcessingState(on, title = '', detail = '') {
  busy = on;
  $('processing').hidden = !on;
  $('processing-title').textContent = title;
  $('processing-detail').textContent = detail;
  document.querySelector('.app-shell').inert = on;
  $('upload-progress').hidden = false;
  $('upload-progress').value = 0;
  clearInterval(timer);
  if (on) {
    const start = Date.now();
    $('elapsed').textContent = '0 seconds elapsed';
    timer = setInterval(() => {
      $('elapsed').textContent = `${Math.floor((Date.now()-start)/1000)} seconds elapsed`;
    }, 1000);
  }
  renderFileList();
  if (!on) revealNotice();
}
async function extractSelectedFiles() {
  if (!files.length) throw new Error('Add a PDF, DOCX, or PPTX to get started.');
  const body = new FormData();
  files.forEach(f => body.append('files', f));
  const result = await request('/api/extract', body, p => {
    $('upload-progress').value = p;
    if (p === 100) $('processing-detail').textContent =
      'Upload complete. Extracting document text…';
  });
  documents = result.files;
  renderFileList();
  $('preview-panel').hidden = false;
  $('extraction-stats').textContent =
    `${result.characters.toLocaleString()} characters · ~${result.approximate_tokens.toLocaleString()} tokens · ${documents.length} documents`;
  $('preview').innerHTML = documents.map(d =>
    `<details><summary>${e(d.filename)} · ${d.sections.length} sections</summary>${d.sections.map(s=>`<h3>${d.source_type==='docx'?'Section':d.source_type==='pptx'?'Slide':'Page'} ${s.page}: ${e(s.title)}</h3><pre>${e(s.content)}</pre>`).join('')}</details>`
    ).join('');
  $('step-config').classList.add('active');
}
$('extract').onclick = async () => {
  if (busy) return;
  notify('');
  setProcessingState(true, 'Reading your documents…',
    'Uploading and extracting readable content.');
  try {
    await extractSelectedFiles();
  } catch (err) {
    notify(err.message);
  } finally {
    setProcessingState(false);
  }
};
$('generate').onclick = async () => {
  if (busy) return;
  notify('');
  if (!selectedTypes().length) return notify('Choose at least one material type.');
  const language = $('language').value === 'Other' ? $('custom-language').value.trim() : $(
    'language').value;
  if (!language) return notify('Enter the language you want to study in.');
  if (!files.length) return notify('Upload your study materials first, or try the demo.');
  let result;
  setProcessingState(true, 'Preparing your study session…',
    'Reading and extracting your documents.');
  try {
    if (!documents.length) await extractSelectedFiles();
    $('processing-title').textContent = 'Creating your study materials…';
    $('processing-detail').textContent =
      'Documents extracted. Gemini is analyzing sources and generating resources. Large documents are summarized in stages; the result is validated before display.';
    $('upload-progress').hidden = true;
    result = await request('/api/generate', {
      files: documents,
      material_types: selectedTypes(),
      difficulty: $('difficulty').value,
      question_difficulty: $('question-difficulty').value,
      question_count: Number($('question-count').value),
      language,
      learning_style: $('learning-style').value
    });
  } catch (err) {
    notify(err.message);
  } finally {
    setProcessingState(false);
  }
  if (result) setMaterial(result);
};
$('demo').onclick = async () => {
  if (busy) return;
  try {
    const result = await fetch('assets/demo.json');
    if (!result.ok) throw new Error('Could not load the demo.');
    notify('');
    setMaterial(await result.json());
  } catch (err) {
    notify(err.message);
  }
};

function renderCards() {
  const container = $('view-flashcards');
  if (!material.flashcards.length) {
    container.innerHTML = empty('flashcards');
    return;
  }
  const sourceCardIndex = cardOrder[cardIndex],
    card = material.flashcards[sourceCardIndex];
  container.innerHTML = heading('Make it stick. One card at a time.',
      'Tap to reveal. Space to flip. Arrow keys to navigate.', 'gallery-vertical-end') +
    `<p class="counter">CARD ${cardIndex+1} / ${cardOrder.length} · ${known.size} KNOWN · ${again.size} TO REVIEW</p><div class="flash-wrap"><button class="flashcard" id="flashcard" aria-label="Flashcard question: ${e(card.question)}. Activate to reveal answer." aria-pressed="false"><span class="flash-face"><small>THINK IT THROUGH</small><strong>${e(card.question)}</strong><small>Click or press Space to reveal</small></span><span class="flash-face flash-back" aria-hidden="true"><small>THE ANSWER</small><strong>${e(card.answer)}</strong>${source(card.source_reference)}</span></button></div><div class="toolbar"><button class="button secondary" data-card="previous">← Previous</button><button class="button secondary" data-card="shuffle"><i data-lucide="shuffle"></i>Shuffle</button><button class="button secondary" data-card="next">Next →</button></div><div class="toolbar"><button class="button secondary" data-card="again" aria-pressed="${again.has(sourceCardIndex)}">Review again</button><button class="button primary" data-card="known" aria-pressed="${known.has(sourceCardIndex)}"><i data-lucide="check"></i>I know this</button><button class="button secondary" data-card="image">Save image</button></div><p class="help center">${known.has(sourceCardIndex)?'Marked as known.':again.has(sourceCardIndex)?'Marked for another review.':'A little repetition goes a long way.'}</p>`;
}

function flip() {
  const card = $('flashcard');
  if (!card) return;
  const flipped = card.classList.toggle('flipped');
  card.setAttribute('aria-pressed', flipped);
  card.querySelector('.flash-face').setAttribute('aria-hidden', flipped);
  card.querySelector('.flash-back').setAttribute('aria-hidden', !flipped);
  const item = material.flashcards[cardOrder[cardIndex]];
  card.setAttribute('aria-label', flipped ? `Answer: ${item.answer}. Activate to see question.` :
    `Question: ${item.question}. Activate to reveal answer.`);
}

function cardAction(action) {
  if (!material?.flashcards.length) return;
  const sourceCardIndex = cardOrder[cardIndex];
  if (action === 'previous') cardIndex = (cardIndex - 1 + cardOrder.length) % cardOrder.length;
  if (action === 'next') cardIndex = (cardIndex + 1) % cardOrder.length;
  if (action === 'shuffle') {
    for (let i = cardOrder.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [cardOrder[i], cardOrder[j]] = [cardOrder[j], cardOrder[i]];
    }
    cardIndex = 0;
  }
  if (action === 'known') {
    known.add(sourceCardIndex);
    again.delete(sourceCardIndex);
  }
  if (action === 'again') {
    again.add(sourceCardIndex);
    known.delete(sourceCardIndex);
  }
  if (action === 'image') {
    const card = material.flashcards[sourceCardIndex];
    cardImage(material.title,
      `${card.question}\n\n${card.answer}\n\nSource: ${card.source_reference.file} — ${card.source_reference.page}`
      );
  } else {
    renderCards();
    icons();
  }
}
document.addEventListener('keydown', event => {
  if (currentView !== 'flashcards' || busy || event.target.closest('input,textarea,select,a'))
    return;
  if (event.code === 'Space' && !event.target.closest('button')) {
    event.preventDefault();
    flip();
  }
  if (event.code === 'ArrowLeft') {
    event.preventDefault();
    cardAction('previous');
  }
  if (event.code === 'ArrowRight') {
    event.preventDefault();
    cardAction('next');
  }
});

function currentQuestions() {
  return material?.[mode] || [];
}

function renderQuiz() {
  const container = $('view-quiz');
  const modes = [
    ['quiz', 'Multiple choice'],
    ['identification', 'Identification'],
    ['true_false', 'True or false'],
    ['fill_in_the_blank', 'Fill in the blank']
  ];
  const quizQuestions = currentQuestions();
  container.innerHTML = heading('A little practice. A lot more confidence.',
      'Check what you know and learn from what you miss.', 'list-checks') +
    `<div class="quiz-modes">${modes.map(([modeValue,modeLabel])=>`<button class="button ${mode===modeValue?'primary':'secondary'}" data-mode="${modeValue}" aria-pressed="${mode===modeValue}">${modeLabel} (${material[modeValue].length})</button>`).join('')}</div>`;
  if (!quizQuestions.length) {
    container.innerHTML += empty('questions for this activity');
    return;
  }
  if (questionIndex >= quizQuestions.length) {
    const score = answers.filter(Boolean).length;
    container.innerHTML +=
      `<div class="panel question-panel center"><span class="eyebrow">LOOK HOW FAR YOU’VE COME</span><h2>Quiz complete</h2><div class="score-number">${Math.round(score/quizQuestions.length*100)}%</div><h3>Score: ${score} / ${quizQuestions.length}</h3><p>Correct: ${score} · Incorrect: ${quizQuestions.length-score}</p><div class="toolbar"><button class="button primary" data-quiz="restart">Practice again</button></div></div>`;
    return;
  }
  const question = quizQuestions[questionIndex],
    choices = mode === 'quiz' ? question.choices : mode === 'true_false' ? ['True', 'False'] : null;
  container.innerHTML +=
    `<section class="panel question-panel"><p class="counter">QUESTION ${questionIndex+1} OF ${quizQuestions.length} · SCORE ${answers.filter(Boolean).length}</p><div class="reading-progress"><progress aria-label="Quiz questions completed" max="${quizQuestions.length}" value="${questionIndex}"></progress></div><h2>${e(question.question||question.statement)}</h2>${choices?`<div class="choices">${choices.map((c,i)=>`<button class="choice" data-choice="${i}" aria-pressed="false">${String.fromCharCode(65+i)}. ${e(c)}</button>`).join('')}</div>`:`<label for="practice-answer">Your answer</label><input class="practice-input" id="practice-answer" autocomplete="off" placeholder="Type your answer">`}<div id="quiz-feedback" aria-live="polite"></div><div class="toolbar"><button class="button primary" data-quiz="submit">Submit answer</button>${!choices?'<button class="button secondary" data-quiz="reveal">Reveal answer</button>':''}<button class="button primary" data-quiz="next" hidden>Next question →</button></div></section>`;
}

function submitAnswer(reveal = false) {
  if (submitted) return;
  const question = currentQuestions()[questionIndex];
  let response;
  if (mode === 'quiz' || mode === 'true_false') {
    if (selected === null) return notify('Choose an answer first.');
    response = mode === 'quiz' ? question.choices[selected] : selected === 0;
  } else {
    response = $('practice-answer').value.trim();
    if (!response && !reveal) return notify('Enter an answer, or choose Reveal answer.');
  }
  notify('');
  const expected = mode === 'quiz' ? question.correct_answer : question.answer;
  const normalize = x => String(x).normalize('NFKC').toLowerCase().replace(/[.,!?;:]+$/, '').trim();
  const correct = !reveal && normalize(response) === normalize(expected);
  answers.push(correct);
  submitted = true;
  document.querySelectorAll('[data-choice]').forEach(button => {
    const choiceValue = mode === 'quiz' ? question.choices[Number(button.dataset.choice)] : Number(button.dataset
      .choice) === 0;
    button.disabled = true;
    button.classList.toggle('correct', choiceValue === expected);
    button.classList.toggle('incorrect', Number(button.dataset.choice) === selected && !
    correct);
  });
  if ($('practice-answer')) $('practice-answer').disabled = true;
  $('quiz-feedback').innerHTML =
    `<div class="feedback"><strong>${reveal?'Answer revealed (not scored as correct)':correct?'Correct — nicely done!':'Not quite. Here’s the answer:'}</strong><p>${e(String(expected))}</p>${question.explanation?`<p>${e(question.explanation)}</p>`:''}${source(question.source_reference)}${!['quiz','true_false'].includes(mode)?'<small>Text answers use normalized exact matching. Equivalent wording may be marked incorrect.</small>':''}</div>`;
  document.querySelector('[data-quiz=submit]').disabled = true;
  const revealButton = document.querySelector('[data-quiz=reveal]');
  if (revealButton) revealButton.disabled = true;
  document.querySelector('[data-quiz=next]').hidden = false;
}

function updateReadingProgress() {
  if ($('read-count')) {
    $('read-count').textContent =
      `${readTopics.size} of ${material.topics.length} topics marked read`;
    $('read-progress').value = readTopics.size;
  }
}
$('main').addEventListener('change', event => {
  if (event.target.matches('[data-read]')) {
    const id = Number(event.target.dataset.read);
    event.target.checked ? readTopics.add(id) : readTopics.delete(id);
    updateReadingProgress();
  }
});

function materialForDownload() {
  if ($('download-scope').value === 'all') return {
    data: material,
    suffix: 'all-materials'
  };
  const data = {
    title: material.title,
    source_files: material.source_files,
    warnings: material.warnings,
    summary: null,
    topics: [],
    flashcards: [],
    quiz: [],
    identification: [],
    true_false: [],
    fill_in_the_blank: [],
    key_terms: [],
    study_guide: null
  };
  let suffix = currentView;
  if (currentView === 'reviewer') {
    data.summary = material.summary;
    data.topics = material.topics;
  }
  if (currentView === 'flashcards') data.flashcards = material.flashcards;
  if (currentView === 'quiz') {
    data[mode] = material[mode];
    suffix = mode;
  }
  if (currentView === 'key_terms') data.key_terms = material.key_terms.length ? material.key_terms :
    material.topics.flatMap(t => t.key_terms);
  if (currentView === 'study_guide') data.study_guide = material.study_guide;
  return {
    data,
    suffix
  };
}

function downloadMaterial(format) {
  if (!material) return;
  const {
    data,
    suffix
  } = materialForDownload();
  const fields = ['summary', 'topics', 'flashcards', 'quiz', 'identification', 'true_false',
    'fill_in_the_blank', 'key_terms', 'study_guide'
  ];
  if (!fields.some(key => Array.isArray(data[key]) ? data[key].length : data[key])) {
    notify(
      'No content in this material yet. Select “All materials” or generate this material first.');
    return;
  }
  notify('');
  const name =
    `${material.title.replace(/[^\p{L}\p{N} _-]/gu, '').trim().slice(0, 80) || 'Reviewarudo'}-${suffix}`;
  if (format === 'json') download(name + '.json', JSON.stringify(data, null, 2),
  'application/json');
  if (format === 'text') {
    const content = Object.fromEntries(Object.entries(data).filter(([, value]) => value !== null &&
      (!Array.isArray(value) || value.length)));
    download(name + '.txt', asText(content), 'text/plain;charset=utf-8');
  }
  if (format === 'print') printMaterial(data);
}

function handleStudyAction(event) {
  const button = event.target.closest('button');
  if (!button || busy) return;
  if (button.dataset.view) {
    showView(button.dataset.view);
    return;
  }
  if (button.dataset.resource) {
    const resource = button.dataset.resource;
    if (['quiz', 'identification', 'true_false', 'fill_in_the_blank'].includes(resource)) {
      mode = resource;
      resetQuizProgress();
      showView('quiz');
    } else showView(resource === 'summary' ? 'reviewer' : resource);
    return;
  }
  if (button.dataset.download) {
    downloadMaterial(button.dataset.download);
    return;
  }
  if (button.hasAttribute('data-go-upload')) showView('upload');
  if (button.id === 'flashcard') flip();
  if (button.dataset.card) cardAction(button.dataset.card);
  if (button.dataset.mode) {
    mode = button.dataset.mode;
    resetQuizProgress();
    renderQuiz();
    icons();
  }
  if (button.dataset.choice !== undefined && !submitted) {
    selected = Number(button.dataset.choice);
    document.querySelectorAll('[data-choice]').forEach(x => {
      x.classList.toggle('selected', x === button);
      x.setAttribute('aria-pressed', x === button);
    });
  }
  if (button.dataset.quiz === 'submit') submitAnswer();
  if (button.dataset.quiz === 'reveal') submitAnswer(true);
  if (button.dataset.quiz === 'next' && submitted) {
    questionIndex++;
    selected = null;
    submitted = false;
    renderQuiz();
    icons();
  }
  if (button.dataset.quiz === 'restart') {
    resetQuizProgress();
    renderQuiz();
    icons();
  }
  if (button.dataset.export === 'json') download('reviewarudo.json', JSON.stringify(material, null,
    2), 'application/json');
  if (button.dataset.export === 'text') download('reviewarudo.txt', asText(material),
    'text/plain;charset=utf-8');
  if (button.dataset.export === 'print') printMaterial(material);
  if (button.dataset.sectionImage !== undefined) {
    const t = material.topics[Number(button.dataset.sectionImage)];
    cardImage(t.title,
      `${t.summary}\n\n${t.key_points.join('\n')}\n\nSource: ${t.source_reference.file} — ${t.source_reference.page}`
      );
  }
}
$('main').addEventListener('click', handleStudyAction);

let savedTheme = null;
try {
  savedTheme = localStorage.getItem('reviewarudo-theme');
} catch {}

function applyTheme(dark) {
  document.documentElement.classList.toggle('dark', dark);
  document.documentElement.style.colorScheme = dark ? 'dark' : 'light';
  const label = dark ? 'Light mode' : 'Dark mode';
  $('theme').innerHTML = `<i data-lucide="${dark ? 'sun' : 'moon'}"></i><span>${label}</span>`;
  $('theme').setAttribute('aria-label', `Switch to ${label.toLowerCase()}`);
  $('theme').setAttribute('title', `Switch to ${label.toLowerCase()}`);
  $('theme').setAttribute('aria-pressed', String(dark));
  document.querySelector('meta[name="theme-color"]').content = dark ? '#07070d' : '#f6f3ff';
  icons();
}
applyTheme(savedTheme !== 'light');
$('theme').onclick = () => {
  const dark = !document.documentElement.classList.contains('dark');
  savedTheme = dark ? 'dark' : 'light';
  applyTheme(dark);
  try {
    localStorage.setItem('reviewarudo-theme', savedTheme);
  } catch {}
};

window.addEventListener('storage', event => {
  if (event.key === 'reviewarudo-theme' || event.key === null) {
    savedTheme = event.newValue;
    applyTheme(savedTheme !== 'light');
  }
});
$('clear').onclick = () => {
  if (busy || !confirm(
      'Clear this study session and its generated materials? Export anything you want to keep first.'
      )) return;
  material = null;
  files = [];
  documents = [];
  try {
    sessionStorage.removeItem('reviewarudo-material');
  } catch {}
  invalidateExtraction();
  for (const view of Object.keys(VIEW_LABELS).filter(x => x !== 'upload')) $('view-' + view)
    .replaceChildren();
  $('print-content').replaceChildren();
  $('step-study').classList.remove('active');
  showView('upload');
  notify('');
};
updateStudySet();
showView('upload');
window.addEventListener('load', icons);
