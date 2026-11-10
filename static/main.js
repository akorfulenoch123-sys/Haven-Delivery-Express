const toggle = document.getElementById("hamburger");
const nav = document.getElementById("navlinks");
if (toggle && nav) toggle.addEventListener("click", () => nav.classList.toggle("open"));
document.querySelectorAll(".flash").forEach(el => setTimeout(() => { el.style.opacity = "0.97"; }, 100));
const copyBtn = document.getElementById("copyCode");
if (copyBtn) copyBtn.addEventListener("click", async () => {
  const code = copyBtn.dataset.code;
  try { await navigator.clipboard.writeText(code); copyBtn.textContent = "Copied!"; }
  catch (_) { window.prompt("Copy your tracking code:", code); }
});
