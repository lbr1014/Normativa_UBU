document.addEventListener("DOMContentLoaded", () => {
  const progressBox = document.getElementById("scraping-progress");
  const bar = progressBox?.querySelector(".progress-bar");
  const text = progressBox?.querySelector(".progress-text");

  const scrapingForm = document.getElementById("scrapingForm");
  const vectorForm = document.getElementById("vectorForm");
  const uploadForm = document.getElementById("uploadForm");

  function toggleButtons(disabled) {
    uploadForm?.querySelectorAll("button").forEach((button) => {
      button.disabled = disabled;
    });
  }

  function showProgressBox() {
    if (!progressBox) return;
    progressBox.classList.remove("d-none");
    progressBox.style.display = "block";
  }

  function setUIRunning(message) {
    showProgressBox();

    if (text) {
      text.textContent = message;
    }

    if (bar) {
      bar.style.animation = "none";
      bar.style.width = "0%";
    }

    toggleButtons(true);
  }

  function setUIProgress(percent, message) {
    if (!progressBox || !bar) return;

    showProgressBox();
    bar.style.animation = "none";
    bar.style.width = `${Math.max(0, Math.min(100, percent))}%`;

    if (text) {
      text.textContent = message;
    }
  }

  function setUIDone(message) {
    setUIProgress(100, message);
    window.setTimeout(() => window.location.reload(), 600);
  }

  function setUIFailed(message) {
    showProgressBox();

    if (bar) {
      bar.style.animation = "none";
      bar.style.width = "100%";
    }

    if (text) {
      text.textContent = message;
    }

    toggleButtons(false);
  }

  async function fetchJson(url, options = {}) {
    const response = await fetch(url, {
      headers: { Accept: "application/json" },
      ...options,
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    return response.json();
  }

  async function pollVectorJob(jobId) {
    const statusUrl = `/admin/vector-db/status/${jobId}`;

    while (true) {
      try {
        const data = await fetchJson(statusUrl);
        const status = data.status;
        const progress = Number(data.progress ?? 0);
        const currentDoc = data.current_doc;

        if (status === "running" || status === "queued") {
          const message = currentDoc
            ? `Actualizando base vectorial... (${progress}%) - ${currentDoc}`
            : `Actualizando base vectorial... (${progress}%)`;
          setUIProgress(progress, message);
          await new Promise((resolve) => window.setTimeout(resolve, 1000));
          continue;
        }

        sessionStorage.removeItem("vector_job_id");

        if (status === "done") {
          setUIDone("Base vectorial actualizada.");
          return;
        }

        if (status === "failed") {
          const error = data.error ? ` Error: ${data.error}` : "";
          setUIFailed(`Fallo la actualizacion de la base vectorial.${error}`);
          return;
        }

        setUIFailed("Estado de actualizacion desconocido.");
        return;
      } catch (error) {
        setUIFailed("No se pudo consultar el estado del job.");
        return;
      }
    }
  }

  async function startVectorUpdate(event) {
    event.preventDefault();
    if (!vectorForm) return;

    try {
      setUIRunning("Lanzando actualizacion de base vectorial...");
      const data = await fetchJson(vectorForm.action, { method: "POST" });

      if (!data.job_id) {
        setUIFailed("No se recibio el identificador del job.");
        return;
      }

      sessionStorage.setItem("vector_job_id", String(data.job_id));
      setUIProgress(0, "Actualizando base vectorial... (0%)");
      pollVectorJob(data.job_id);
    } catch (error) {
      setUIFailed("No se pudo iniciar la actualizacion.");
    }
  }

  async function pollScrapingJob(jobId) {
    const statusUrl = `/admin/documents/web_scraping/status/${jobId}`;

    while (true) {
      try {
        const data = await fetchJson(statusUrl);
        const status = data.status;
        const progress = Number(data.progress ?? 0);
        const message = data.message || `Web scraping... (${progress}%)`;

        if (status === "running" || status === "queued") {
          setUIProgress(progress, message);
          await new Promise((resolve) => window.setTimeout(resolve, 1000));
          continue;
        }

        sessionStorage.removeItem("scraping_job_id");

        if (status === "done") {
          setUIDone("Web scraping completado.");
          return;
        }

        if (status === "failed") {
          const error = data.error ? ` Error: ${data.error}` : "";
          setUIFailed(`Fallo el web scraping.${error}`);
          return;
        }

        setUIFailed("Estado de scraping desconocido.");
        return;
      } catch (error) {
        setUIFailed("No se pudo consultar el estado del scraping.");
        return;
      }
    }
  }

  async function startScraping(event) {
    event.preventDefault();
    if (!scrapingForm) return;

    try {
      setUIRunning("Lanzando web scraping...");
      const data = await fetchJson(scrapingForm.action, { method: "POST" });

      if (!data.job_id) {
        setUIFailed("No se recibio el identificador del scraping.");
        return;
      }

      sessionStorage.setItem("scraping_job_id", String(data.job_id));
      setUIProgress(0, "Web scraping... (0%)");
      pollScrapingJob(data.job_id);
    } catch (error) {
      setUIFailed("No se pudo iniciar el web scraping.");
    }
  }

  vectorForm?.addEventListener("submit", startVectorUpdate);
  scrapingForm?.addEventListener("submit", startScraping);

  const savedVectorJobId = sessionStorage.getItem("vector_job_id");
  if (savedVectorJobId) {
    setUIRunning("Reanudando seguimiento de la actualización...");
    pollVectorJob(savedVectorJobId);
  }

  const savedScrapingJobId = sessionStorage.getItem("scraping_job_id");
  if (savedScrapingJobId) {
    setUIRunning("Reanudando seguimiento del web scraping...");
    pollScrapingJob(savedScrapingJobId);
  }
});
