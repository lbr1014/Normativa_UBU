document.addEventListener('click', function (e) {
  const dropdowns = document.querySelectorAll('.dropdown');

  dropdowns.forEach(dropdown => {
    const button = dropdown.querySelector('.dropdown-toggle');

    if (button && button.contains(e.target)) {
      dropdown.classList.toggle('open');
    } else {
      dropdown.classList.remove('open');
    }
  });
});
