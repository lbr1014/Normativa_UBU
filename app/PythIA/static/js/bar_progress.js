document.addEventListener("DOMContentLoaded", () => {
  const progressBox = document.getElementById("scraping-progress");
  const bar = progressBox?.querySelector(".progress-bar");
  const text = progressBox?.querySelector(".progress-text");
  const cancelButton = document.getElementById("cancel-job-button");

  const scrapingForm = document.getElementById("scrapingForm");
  const vectorForm = document.getElementById("vectorForm");
  const markdownForm = document.getElementById("markdownForm");
  const uploadForm = document.getElementById("uploadForm");

  let activeJob = null;

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

  function setCancelVisible(visible) {
    if (!cancelButton) return;
    cancelButton.classList.toggle("d-none", !visible);
    cancelButton.disabled = false;
  }

  function setActiveJob(type, jobId) {
    activeJob = type && jobId ? { type, jobId: String(jobId) } : null;
    if (activeJob) {
      sessionStorage.setItem("admin_active_job_type", activeJob.type);
      sessionStorage.setItem("admin_active_job_id", activeJob.jobId);
      setCancelVisible(true);
      return;
    }

    sessionStorage.removeItem("admin_active_job_type");
    sessionStorage.removeItem("admin_active_job_id");
    setCancelVisible(false);
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
    setActiveJob(null, null);
    window.setTimeout(() => window.location.reload(), 600);
  }

  function setUICancelled(message) {
    setUIProgress(0, message);
    setActiveJob(null, null);
    toggleButtons(false);
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
    setActiveJob(null, null);
    toggleButtons(false);
  }

  async function fetchJson(url, options = {}) {
    const response = await fetch(url, {
      headers: { Accept: "application/json" },
      ...options,
    });

    let data = {};
    try {
      data = await response.json();
    } catch (error) {
      data = {};
    }

    if (!response.ok) {
      throw new Error(data.error || `HTTP ${response.status}`);
    }

    return data;
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

        if (status === "done") {
          setUIDone("Base vectorial actualizada.");
          return;
        }

        if (status === "cancelled") {
          setUICancelled("Actualizacion vectorial cancelada.");
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

      setActiveJob("vector", data.job_id);
      setUIProgress(0, "Actualizando base vectorial... (0%)");
      pollVectorJob(data.job_id);
    } catch (error) {
      setUIFailed("No se pudo iniciar la actualizacion.");
    }
  }

  async function pollMarkdownJob(jobId) {
    const statusUrl = `/admin/documents/markdown/status/${jobId}`;

    while (true) {
      try {
        const data = await fetchJson(statusUrl);
        const status = data.status;
        const progress = Number(data.progress ?? 0);
        const message = data.message || `Convirtiendo documentos a Markdown... (${progress}%)`;

        if (status === "running" || status === "queued") {
          setUIProgress(progress, message);
          await new Promise((resolve) => window.setTimeout(resolve, 1000));
          continue;
        }

        if (status === "done") {
          setUIDone(data.message || "Conversion a Markdown completada.");
          return;
        }

        if (status === "cancelled") {
          setUICancelled(data.message || "Conversion a Markdown cancelada.");
          return;
        }

        if (status === "failed") {
          const error = data.error ? ` Error: ${data.error}` : "";
          setUIFailed(`Fallo la conversion a Markdown.${error}`);
          return;
        }

        setUIFailed("Estado de conversion desconocido.");
        return;
      } catch (error) {
        setUIFailed("No se pudo consultar el estado de la conversion.");
        return;
      }
    }
  }

  async function startMarkdownConversion(event) {
    event.preventDefault();
    if (!markdownForm) return;

    try {
      setUIRunning("Lanzando conversion a Markdown...");
      const data = await fetchJson(markdownForm.action, { method: "POST" });

      if (!data.job_id) {
        setUIFailed("No se recibio el identificador del job.");
        return;
      }

      setActiveJob("markdown", data.job_id);
      setUIProgress(0, "Convirtiendo documentos a Markdown... (0%)");
      pollMarkdownJob(data.job_id);
    } catch (error) {
      setUIFailed("No se pudo iniciar la conversion a Markdown.");
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

        if (status === "done") {
          setUIDone("Web scraping completado.");
          return;
        }

        if (status === "cancelled") {
          setUICancelled("Web scraping cancelado.");
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

      setActiveJob("scraping", data.job_id);
      setUIProgress(0, "Web scraping... (0%)");
      pollScrapingJob(data.job_id);
    } catch (error) {
      setUIFailed("No se pudo iniciar el web scraping.");
    }
  }

  async function cancelActiveJob() {
    if (!activeJob || !cancelButton) return;

    cancelButton.disabled = true;
    try {
      if (activeJob.type === "vector") {
        await fetchJson(`/admin/vector-db/cancel/${activeJob.jobId}`, { method: "POST" });
        setUIProgress(bar ? parseInt(bar.style.width || "0", 10) || 0 : 0, "Cancelando actualizacion vectorial...");
      } else if (activeJob.type === "markdown") {
        await fetchJson(`/admin/documents/markdown/cancel/${activeJob.jobId}`, { method: "POST" });
        setUIProgress(bar ? parseInt(bar.style.width || "0", 10) || 0 : 0, "Cancelando conversion a Markdown...");
      } else if (activeJob.type === "scraping") {
        await fetchJson(`/admin/documents/web_scraping/cancel/${activeJob.jobId}`, { method: "POST" });
        setUIProgress(bar ? parseInt(bar.style.width || "0", 10) || 0 : 0, "Cancelando web scraping...");
      }
    } catch (error) {
      cancelButton.disabled = false;
      setUIFailed(error.message || "No se pudo cancelar el proceso.");
    }
  }

  vectorForm?.addEventListener("submit", startVectorUpdate);
  markdownForm?.addEventListener("submit", startMarkdownConversion);
  scrapingForm?.addEventListener("submit", startScraping);
  cancelButton?.addEventListener("click", cancelActiveJob);

  const savedType = sessionStorage.getItem("admin_active_job_type");
  const savedId = sessionStorage.getItem("admin_active_job_id");
  if (savedType && savedId) {
    setActiveJob(savedType, savedId);
    setUIRunning("Reanudando seguimiento del proceso...");
    if (savedType === "vector") {
      pollVectorJob(savedId);
    } else if (savedType === "markdown") {
      pollMarkdownJob(savedId);
    } else if (savedType === "scraping") {
      pollScrapingJob(savedId);
    }
  }
});
