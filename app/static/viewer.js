/* Mozilla PDF.js renders the document, selectable text and interactive form layer. */
import * as pdfjsLib from '/vendor/pdfjs/pdf.mjs';
import {EventBus, PDFViewer, PDFLinkService, PDFFindController} from '/vendor/pdfjs/pdf_viewer.mjs';

pdfjsLib.GlobalWorkerOptions.workerSrc = '/vendor/pdfjs/pdf.worker.mjs';
const $ = selector => document.querySelector(selector);

export function createDocumentViewer(getToken) {
  const bus = new EventBus();
  const links = new PDFLinkService({eventBus: bus, externalLinkTarget: 2 /* PDF.js LinkTarget.BLANK */});
  const find = new PDFFindController({eventBus: bus, linkService: links});
  const viewer = new PDFViewer({
    container: $('#pdf-container'), viewer: $('#pdf-pages'), eventBus: bus,
    linkService: links, findController: find, annotationMode: pdfjsLib.AnnotationMode.ENABLE_FORMS,
    enableScripting: false, enableAutoLinking: false,
    imageResourcesPath: '/vendor/pdfjs/images/', maxCanvasPixels: 10000000
  });
  links.setViewer(viewer);
  let current = null, document = null, task = null, generation = 0, dirty = false, saving = false;
  let revision = 0, fingerprint = '', savedValues = {}, timer = null, editSerial = 0;

  const status = (message, error = false) => {
    $('#document-status').textContent = message;
    $('#document-status').classList.toggle('save-error', error);
    $('#save-document').disabled = !document || !dirty || saving;
  };
  const message = (text, error = false) => {
    $('#viewer-message').textContent = text;
    $('#viewer-message').hidden = !text;
    $('#viewer-message').classList.toggle('save-error', error);
  };
  const values = () => {
    const result = {...savedValues};
    const changes = document?.annotationStorage.serializable.map || new Map();
    for (const [id, data] of changes) {
      if (Object.hasOwn(data, 'value')) result[id] = {value: data.value};
    }
    return result;
  };
  async function save() {
    if (!document || !dirty || saving) return false;
    clearTimeout(timer);
    const docGeneration = generation, serial = editSerial, formValues = values();
    saving = true; status('Saving…');
    try {
      const response = await fetch('/api/document', {
        method: 'POST', headers: {'Content-Type': 'application/json', 'X-PACE-Token': getToken()},
        body: JSON.stringify({id: current.project.id, file: current.file.name, fingerprint, revision, values: formValues})
      });
      const result = await response.json();
      if (!response.ok) throw Error(result.error || 'Could not save form state.');
      if (generation !== docGeneration) return false;
      revision = result.revision; savedValues = formValues;
      dirty = editSerial !== serial;
      status(dirty ? 'Unsaved changes' : 'Changes saved on the server');
      if (dirty) timer = setTimeout(save, 900);
      return true;
    } catch (error) {
      if (generation === docGeneration) status(error.message + ' Your changes remain in this view.', true);
      return false;
    } finally {
      if (generation === docGeneration) {saving = false; $('#save-document').disabled = !dirty;}
    }
  }
  function changed() {
    if (!document) return;
    editSerial++; dirty = true; status('Unsaved changes');
    clearTimeout(timer); timer = setTimeout(save, 900);
  }
  $('#pdf-container').addEventListener('change', event => {
    if (event.target.matches('.annotationLayer input, .annotationLayer textarea, .annotationLayer select')) changed();
  });
  $('#pdf-container').addEventListener('input', event => {
    if (event.target.matches('.annotationLayer input:not([type=checkbox]):not([type=radio]), .annotationLayer textarea')) changed();
  });
  $('#save-document').onclick = save;
  $('#download-document').onclick = async () => {
    if (!document) return;
    try {
      const bytes = document.annotationStorage.size ? await document.saveDocument() : await document.getData();
      const url = URL.createObjectURL(new Blob([bytes], {type: 'application/pdf'}));
      const a = window.document.createElement('a'); a.href = url; a.download = current.file.name;
      a.click(); setTimeout(() => URL.revokeObjectURL(url), 30000);
    } catch (error) {status('Download failed: ' + error.message, true);}
  };
  $('#previous-page').onclick = () => {if (document) viewer.currentPageNumber--;};
  $('#next-page').onclick = () => {if (document) viewer.currentPageNumber++;};
  $('#page-number').onchange = event => {
    if (document) viewer.currentPageNumber = Math.max(1, Math.min(document.numPages, Number(event.target.value) || 1));
  };
  $('#zoom-in').onclick = () => {if (document) viewer.currentScale = Math.min(4, viewer.currentScale * 1.2);};
  $('#zoom-out').onclick = () => {if (document) viewer.currentScale = Math.max(.2, viewer.currentScale / 1.2);};
  $('#zoom-mode').onchange = event => {if (document) viewer.currentScaleValue = event.target.value;};
  const search = (again = false, backwards = false) => {
    if (!document) return;
    bus.dispatch('find', {source: window, type: again ? 'again' : '', query: $('#document-search').value,
      caseSensitive: false, entireWord: false, highlightAll: true, findPrevious: backwards, matchDiacritics: false});
  };
  $('#document-search').oninput = () => search();
  $('#document-search').onkeydown = event => {
    if (event.key === 'Enter') {event.preventDefault(); search(true, event.shiftKey);}
  };
  $('#find-next').onclick = () => search(true);
  bus.on('updatefindmatchescount', ({matchesCount}) => {
    $('#search-count').textContent = matchesCount.total ? `${matchesCount.current}/${matchesCount.total}` : '';
  });
  bus.on('updatefindcontrolstate', ({state}) => {
    if (state === 1) $('#search-count').textContent = 'No matches';
  });
  bus.on('pagechanging', ({pageNumber}) => {
    $('#page-number').value = pageNumber;
    $('#previous-page').disabled = pageNumber <= 1;
    $('#next-page').disabled = !document || pageNumber >= document.numPages;
  });
  bus.on('scalechanging', ({scale}) => {$('#zoom-label').textContent = Math.round(scale * 100) + '%';});
  bus.on('pagesinit', () => {viewer.currentScaleValue = 'page-width';});
  window.addEventListener('beforeunload', event => {
    if (dirty || saving) {event.preventDefault(); event.returnValue = '';}
  });

  async function canLeave() {
    if (saving) {status('Please wait for the current save to finish.'); return false;}
    if (!dirty) return true;
    if (await save()) return !dirty;
    return window.confirm('These checkbox changes could not be saved. Leave and discard the unsaved changes?');
  }
  async function close() {
    clearTimeout(timer); generation++; dirty = false; saving = false; editSerial = 0;
    document = null; current = null; viewer.setDocument(null); links.setDocument(null); find.setDocument(null);
    if (task) {const previous = task; task = null; await previous.destroy();}
  }
  async function open(project, file) {
    await close();
    const requestGeneration = generation;
    current = {project, file}; status('Loading document…'); message('Loading document…');
    $('#document-title').textContent = project.name;
    $('#document-filename').textContent = file.name;
    $('#document-search').value = ''; $('#search-count').textContent = '';
    $('#page-number').value = 1; $('#page-count').textContent = '—';
    $('#zoom-mode').value = 'page-width';
    for (const id of ['download-document','previous-page','next-page','zoom-in','zoom-out']) $('#' + id).disabled = true;
    try {
      const response = await fetch('/api/document?' + new URLSearchParams({id: project.id, file: file.name}));
      const info = await response.json(); if (!response.ok) throw Error(info.error || 'Cannot load saved form state.');
      if (requestGeneration !== generation) return;
      fingerprint = info.fingerprint; revision = info.revision; savedValues = info.values;
      task = pdfjsLib.getDocument({url: file.url, cMapUrl: '/vendor/pdfjs/cmaps/', cMapPacked: true,
        standardFontDataUrl: '/vendor/pdfjs/standard_fonts/', wasmUrl: '/vendor/pdfjs/wasm/',
        enableScripting: false, isEvalSupported: false, enableXfa: false});
      const pdf = await task.promise;
      if (requestGeneration !== generation) return;
      document = pdf;
      for (const [key, value] of Object.entries(savedValues)) pdf.annotationStorage.setValue(key, value);
      links.setDocument(pdf); find.setDocument(pdf); viewer.setDocument(pdf);
      $('#page-count').textContent = pdf.numPages;
      $('#page-number').max = pdf.numPages;
      for (const id of ['download-document','zoom-in','zoom-out']) $('#' + id).disabled = false;
      $('#next-page').disabled = pdf.numPages <= 1;
      const fields = await pdf.getFieldObjects();
      if (requestGeneration !== generation) return;
      status(fields ? (revision ? 'Saved checkbox state restored' : 'Checkbox changes save automatically') : 'Read-only document · No form fields');
      message('');
    } catch (error) {
      if (requestGeneration === generation) {status('Document could not be opened', true); message(error.message, true);}
    }
  }
  return {open, close, canLeave, save};
}
