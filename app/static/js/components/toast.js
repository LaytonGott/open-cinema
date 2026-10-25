let toast = null;
let timer = null;

/** Show `message` in a bottom-centre alert toast for about 4 seconds. */
export function showToast(message) {
  if (!toast) {
    toast = document.createElement("div");
    toast.setAttribute("data-testid", "toast");
    toast.setAttribute("role", "alert");
    toast.hidden = true;
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(timer);
  timer = setTimeout(() => { toast.hidden = true; }, 4000);
}
