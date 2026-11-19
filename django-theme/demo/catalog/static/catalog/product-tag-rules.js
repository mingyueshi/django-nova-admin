document.querySelectorAll("#product-tag-ranking input[data-minimum-for]").forEach((minimum) => {
  const fields = minimum.form.elements;
  const tags = fields.namedItem(minimum.dataset.minimumFor);
  const mode = fields.namedItem(minimum.dataset.minimumFor + "_mode");
  const maximum = fields.namedItem(minimum.dataset.minimumFor + "_max");

  function update() {
    const range = mode.value === "range";
    const active = range || mode.value === "at_least";
    tags.required = active;
    minimum.required = active;
    minimum.disabled = !active;
    minimum.closest("label").hidden = !active;
    minimum.max = String(Math.max(1, tags.selectedOptions.length));
    maximum.required = range;
    maximum.disabled = !range;
    maximum.closest("label").hidden = !range;
    maximum.max = minimum.max;
    maximum.min = String(Math.max(1, minimum.valueAsNumber || 1));
  }

  mode.addEventListener("change", update);
  tags.addEventListener("change", update);
  minimum.addEventListener("input", update);
  window.addEventListener("pageshow", update);
  update();
});
