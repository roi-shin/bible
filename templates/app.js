// 注の参照クリック → 右パネルでハイライト
document.querySelectorAll('.note-ref').forEach(ref => {
  ref.addEventListener('click', () => {
    const verse = ref.dataset.verse;
    const pos = ref.dataset.pos;
    const noteId = `note-${verse}-${pos}`;
    const noteEl = document.getElementById(noteId);

    if (noteEl) {
      // 全ハイライト解除
      document.querySelectorAll('.note.highlight').forEach(n => n.classList.remove('highlight'));
      // ハイライト
      noteEl.classList.add('highlight');
      
      // スマホの場合は自動で拡大パネルにする
      const reader = document.querySelector('.reader');
      reader.classList.remove('notes-hidden');
      if (window.innerWidth <= 1024) {
        reader.classList.add('notes-expanded');
      }
      
      noteEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  });
});

// スマホ用: 注のハンドルをタップで開閉
const notesHandle = document.getElementById('notesHandle');
if (notesHandle) {
  notesHandle.addEventListener('click', () => {
    document.querySelector('.reader').classList.toggle('notes-expanded');
  });
}

// 注パネル表示切替 ([注] ボタン)
const toggleNotesBtn = document.getElementById('toggleNotes');
if (toggleNotesBtn) {
  toggleNotesBtn.addEventListener('click', () => {
    document.querySelector('.reader').classList.toggle('notes-hidden');
    toggleNotesBtn.classList.toggle('active');
  });
}

// レイアウト切替
const toggleLayoutBtn = document.getElementById('toggleLayout');
if (toggleLayoutBtn) {
  toggleLayoutBtn.addEventListener('click', () => {
    document.querySelector('.reader').classList.toggle('layout-reversed');
    toggleLayoutBtn.classList.toggle('active');
  });
}

// 言語切替
const toggleLangBtn = document.getElementById('toggleLang');
if (toggleLangBtn) {
  const langs = ['ja-only', 'both', 'en-only'];
  let currentLangIdx = 0;
  toggleLangBtn.addEventListener('click', () => {
    document.body.classList.remove('lang-' + langs[currentLangIdx]);
    currentLangIdx = (currentLangIdx + 1) % langs.length;
    if (langs[currentLangIdx] !== 'both') {
      document.body.classList.add('lang-' + langs[currentLangIdx]);
    }
    toggleLangBtn.classList.toggle('active', currentLangIdx !== 0);
  });
}
