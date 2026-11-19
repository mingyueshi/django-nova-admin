/* Submit the same CSRF-protected form as the manual button, one batch at a time. */
(async function continueTask() {
  const panel = document.getElementById("batch-progress");
  let form = panel.querySelector("#batch-continue");
  while (form) {
    const button = form.querySelector("button");
    button.disabled = true;
    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        mode: "same-origin",
      });
      if (!response.ok) throw new Error();
      const page = new DOMParser().parseFromString(await response.text(), "text/html");
      const next = page.getElementById("batch-progress");
      if (!next || next.querySelector('[name="cursor"]')?.value === form.elements.cursor.value) {
        throw new Error();
      }
      panel.replaceChildren(...next.childNodes);
      form = panel.querySelector("#batch-continue");
    } catch {
      button.disabled = false;
      panel.querySelector("#batch-interrupted").hidden = false;
      return;
    }
  }
})();
