(() => {
  const search = document.querySelector('#reading-search');
  if (!search) return;
  const cards = [...document.querySelectorAll('[data-reading]')];
  const status = document.querySelector('#search-status');
  search.addEventListener('input', () => {
    const query = search.value.trim().toLocaleLowerCase();
    let count = 0;
    for (const card of cards) {
      card.hidden = !card.textContent.toLocaleLowerCase().includes(query);
      if (!card.hidden) count++;
    }
    status.textContent = `${count} reflection${count === 1 ? '' : 's'}${query ? ' found' : ''}`;
  });
})();
