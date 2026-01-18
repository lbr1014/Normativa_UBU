async function deleteConsulta(id) {
    if (!confirm("¿Seguro que quieres borrar esta consulta?")) return;

    const baseUrl = document.body.dataset.deleteConsultaUrl;
    if (!baseUrl) {
        alert("URL de borrado no configurada");
        return;
    }

    const url = baseUrl.replace("/0/delete", "/" + id + "/delete");

    const resp = await fetch(url, { method: "POST" });

    let data = null;
    try { data = await resp.json(); } catch (_) {}

    if (!resp.ok || !data || !data.ok) {
        alert(data?.error || "No se pudo borrar la consulta");
        return;
    }

    const row = document.getElementById("consulta-" + id);
    if (row) {
        const detailsRow = row.nextElementSibling;
        row.remove();
        if (detailsRow) detailsRow.remove();
    }
}
