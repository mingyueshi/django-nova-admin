document.querySelectorAll("#product-tag-ranking input[data-minimum-for]").forEach((minimum) => {
  const fields = minimum.form.elements;
  const tags = fields.namedItem(minimum.dataset.minimumFor);
  const mode = fields.namedItem(minimum.dataset.minimumFor + "_mode");

  function update() {
    const active = mode.value === "at_least";
    tags.required = active;
    minimum.required = active;
    minimum.disabled = !active;
    minimum.closest("label").hidden = !active;
    minimum.max = String(Math.max(1, tags.selectedOptions.length));
  }

  mode.addEventListener("change", update);
  tags.addEventListener("change", update);
  window.addEventListener("pageshow", update);
  update();
});
