document.addEventListener("DOMContentLoaded", () => {
  const progress = document.getElementById("scraping-progress");
  const bar = progress?.querySelector(".progress-bar");
  const text = progress?.querySelector(".progress-text");

  const scrapingForm = document.querySelector(
    'form[action="/admin/documents/web_scraping"]'
  );

  const updateForm = document.querySelector(
    'form[action="/admin/vector-db/update"]'
  );

  function showProgress(message, storageKey) {
    sessionStorage.setItem(storageKey, "true");

    if (progress) progress.style.display = "block";
    if (text) text.textContent = message;

    document.querySelectorAll("button").forEach(btn => {
      btn.disabled = true;
    });
  }

  function showFinished(message, storageKey) {
    if (sessionStorage.getItem(storageKey) !== "true") return;
    sessionStorage.removeItem(storageKey);

    if (!progress || !bar || !text) return;

    progress.style.display = "block";
    bar.style.animation = "none";
    bar.style.width = "100%";
    text.textContent = message;

    setTimeout(() => {
      progress.style.display = "none";
      bar.style.width = "";
      bar.style.animation = "";
    }, 5000);
  }

  // CUANDO SE ENVÍA EL FORM WEB SCRAPINGS
  if (scrapingForm) {
    scrapingForm.addEventListener("submit", () => {
      showProgress("Ejecutando web scraping…", "scraping_running");
    });
  }

  // CUANDO SE ENVÍA EL FORM UPDATE
  if (updateForm) {
    updateForm.addEventListener("submit", () => {
      showProgress("Actualizando base vectorial…", "vector_updating");
    });
  }

  // CUANDO VUELVE LA PÁGINA
  showFinished("Web scraping completado", "scraping_running");
  showFinished("Base vectorial actualizada", "vector_updating");
});
