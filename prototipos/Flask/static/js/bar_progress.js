document.addEventListener("DOMContentLoaded", () => {
  const progress = document.getElementById("scraping-progress");
  const bar = progress?.querySelector(".progress-bar");
  const text = progress?.querySelector(".progress-text");

  const scrapingForm = document.querySelector(
    'form[action="/admin/documents/web_scraping"]'
  );

  // CUANDO SE ENVÍA EL FORM
  if (scrapingForm) {
    scrapingForm.addEventListener("submit", () => {
      sessionStorage.setItem("scraping_running", "true");

      progress.style.display = "block";
      text.textContent = "Ejecutando web scraping…";

      document.querySelectorAll("button").forEach(btn => {
        btn.disabled = true;
      });
    });
  }

  // CUANDO VUELVE LA PÁGINA (scraping terminado)
  if (sessionStorage.getItem("scraping_running") === "true") {
    sessionStorage.removeItem("scraping_running");

    progress.style.display = "block";
    bar.style.animation = "none";
    bar.style.width = "100%";
    text.textContent = "Web scraping completado ✔";

    setTimeout(() => {
      progress.style.display = "none";
      bar.style.width = "";
      bar.style.animation = "";
    }, 1500);
  }
});
