// TheChef frontend: a small vanilla-JS single-page app over the JSON API.

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const MEALS = ["breakfast", "lunch", "dinner", "snack"];
const MEAL_ICONS = { breakfast: "🌅", lunch: "🥪", dinner: "🍽️", snack: "🍎" };
const MACROS = [
  ["protein", "Protein", "var(--protein)"],
  ["carbs", "Carbs", "var(--carbs)"],
  ["fat", "Fat", "var(--fat)"],
  ["fiber", "Fiber", "var(--fiber)"],
];

const state = {
  me: null,
  day: localDay(new Date()),
  level: null,
  addMeal: defaultMeal(),
  selectedFood: null,
  recipeTag: null,
};

// ---------- utils ----------

function localDay(d) {
  const z = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
  return z.toISOString().slice(0, 10);
}
function defaultMeal() {
  const h = new Date().getHours();
  return h < 11 ? "breakfast" : h < 15 ? "lunch" : h < 21 ? "dinner" : "snack";
}
const r0 = (n) => Math.round(n ?? 0);
const r1 = (n) => Math.round((n ?? 0) * 10) / 10;
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

async function api(path, { method = "GET", body } = {}) {
  const opts = { method, headers: {}, credentials: "same-origin" };
  if (method !== "GET") {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body ?? {});
  }
  const res = await fetch(`/api${path}`, opts);
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && path !== "/auth/login") {
    showAuth();
    throw new Error("Please log in.");
  }
  if (!res.ok) throw new Error(data.description || data.message || `Error ${res.status}`);
  if (data.news?.length) data.news.forEach((n) => toast(n));
  return data;
}

function toast(msg, isError = false) {
  const el = document.createElement("div");
  el.className = "toast" + (isError ? " err" : "");
  el.textContent = msg;
  $("#toasts").append(el);
  setTimeout(() => el.remove(), 3600);
}

function busy(el, on) {
  if (el) el.hidden = !on;
}

function setError(el, err) {
  el.textContent = err ? err.message || String(err) : "";
}

function fillMealSelects() {
  $$(".meal-select").forEach((sel) => {
    sel.innerHTML = MEALS.map((m) => `<option value="${m}">${MEAL_ICONS[m]} ${cap(m)}</option>`).join("");
    sel.value = state.addMeal;
  });
}

// ---------- navigation ----------

function go(view) {
  $$("main .view").forEach((v) => (v.hidden = v.id !== `view-${view}`));
  $$(".tabbar button").forEach((b) => b.classList.toggle("on", b.dataset.goto === view));
  window.scrollTo(0, 0);
  if (view === "today") loadToday();
  if (view === "me") loadMe();
  if (view === "recipes" && !$("#recipe-list").children.length) browseRecipes();
  if (view === "add") {
    $("#add-target").textContent = `→ ${cap(state.addMeal)}, ${dayLabel(state.day)}`;
    fillMealSelects();
    searchFoods();
  }
}

document.addEventListener("click", (e) => {
  const t = e.target.closest("[data-goto]");
  if (t) go(t.dataset.goto);
});

// ---------- auth ----------

let signupMode = false;

function showAuth() {
  $("#shell").hidden = true;
  $("#view-auth").hidden = false;
}

$("#auth-toggle").addEventListener("click", () => {
  signupMode = !signupMode;
  $("#auth-submit").textContent = signupMode ? "Create account" : "Log in";
  $("#auth-toggle").textContent = signupMode ? "Have an account? Log in" : "New here? Create an account";
  $("#auth-form [name=password]").autocomplete = signupMode ? "new-password" : "current-password";
});

$("#auth-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  try {
    await api(signupMode ? "/auth/signup" : "/auth/login", {
      method: "POST",
      body: { username: f.get("username"), password: f.get("password") },
    });
    setError($("#auth-error"));
    await boot();
  } catch (err) {
    setError($("#auth-error"), err);
  }
});

$("#logout").addEventListener("click", async () => {
  await api("/auth/logout", { method: "POST" });
  location.reload();
});

$("#delete-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!confirm("Delete your account and all your data? This cannot be undone.")) return;
  try {
    await api("/me", { method: "DELETE", body: { password: new FormData(e.target).get("password") } });
    location.reload();
  } catch (err) {
    toast(err.message, true);
  }
});

// ---------- game header ----------

async function refreshGame() {
  const g = await api(`/game?day=${state.day}`);
  $("#lvl-num").textContent = g.level;
  $("#lvl-title").textContent = g.title;
  $("#xp-fill").style.width = `${g.progress * 100}%`;
  $("#streak").textContent = g.streak;
  if (state.level !== null && g.level > state.level) {
    $("#levelup-title").textContent = g.title;
    $("#levelup").hidden = false;
  }
  state.level = g.level;
  return g;
}
$("#levelup-close").addEventListener("click", () => ($("#levelup").hidden = true));

// ---------- today ----------

function dayLabel(day) {
  const today = localDay(new Date());
  const y = new Date(); y.setDate(y.getDate() - 1);
  if (day === today) return "Today";
  if (day === localDay(y)) return "Yesterday";
  return new Date(day + "T12:00").toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

$$("[data-day-shift]").forEach((b) =>
  b.addEventListener("click", () => {
    const d = new Date(state.day + "T12:00");
    d.setDate(d.getDate() + Number(b.dataset.dayShift));
    if (localDay(d) > localDay(new Date())) return;
    state.day = localDay(d);
    loadToday();
  })
);

async function loadToday() {
  $("#day-label").textContent = dayLabel(state.day);
  const [log, game] = await Promise.all([api(`/log?day=${state.day}`), refreshGame()]);
  const t = log.targets;
  $("#setup-nudge").hidden = !!t;

  // Calorie ring
  const goal = t?.kcal || 2000;
  const eaten = log.totals.kcal;
  const frac = Math.min(eaten / goal, 1);
  const ring = $("#kcal-ring");
  ring.style.strokeDashoffset = 326.7 * (1 - frac);
  ring.classList.toggle("over", eaten > goal * 1.1);
  const left = goal - eaten;
  $("#kcal-left").textContent = r0(Math.abs(left));
  $("#kcal-left-label").textContent = left >= 0 ? `kcal left of ${r0(goal)}` : "kcal over";

  // Macro bars
  $("#macro-bars").innerHTML = MACROS.map(([k, label, color]) => {
    const have = log.totals[k];
    const want = t?.[k];
    const pct = want ? Math.min((have / want) * 100, 100) : 0;
    return `<div class="macro">
      <div class="top"><span>${label}</span><span><b>${r0(have)}</b>${want ? ` / ${want} g` : " g"}</span></div>
      <div class="bar"><div class="fill" style="width:${pct}%;background:${color}"></div></div>
    </div>`;
  }).join("");

  // Quests
  $("#today-xp").textContent = game.today_xp ? `+${game.today_xp} XP today` : "";
  $("#quests").innerHTML = game.quests.map((q) => `
    <li class="${q.done ? "done" : ""}">
      <span class="tick">${q.done ? "✓" : ""}</span>
      <div><div class="qt">${esc(q.title)}</div><div class="qd">${esc(q.description)}</div></div>
      <span class="xp">+${q.xp}</span>
    </li>`).join("");

  // Meals
  $("#meals").innerHTML = MEALS.map((m) => {
    const items = log.entries.filter((e) => e.meal === m);
    const kcal = items.reduce((s, e) => s + e.kcal, 0);
    return `<div class="card meal">
      <h3><span>${MEAL_ICONS[m]} ${cap(m)}</span><span class="kcal">${r0(kcal)} kcal</span></h3>
      <ul class="list">${items.map((e) => `
        <li><div class="grow"><div class="name">${esc(e.name)}</div>
          <div class="sub">${e.grams ? r0(e.grams) + " g · " : ""}${r0(e.kcal)} kcal · P ${r1(e.protein)} · C ${r1(e.carbs)} · F ${r1(e.fat)}</div></div>
          <button class="x" data-del-log="${e.id}" aria-label="Remove">✕</button></li>`).join("")}
      </ul>
      <button class="btn small" data-add-meal="${m}">+ Add to ${m}</button>
    </div>`;
  }).join("");
}

$("#meals").addEventListener("click", async (e) => {
  const del = e.target.closest("[data-del-log]");
  if (del) {
    await api(`/log/${del.dataset.delLog}`, { method: "DELETE" });
    return loadToday();
  }
  const add = e.target.closest("[data-add-meal]");
  if (add) {
    state.addMeal = add.dataset.addMeal;
    go("add");
  }
});

// ---------- add food ----------

function setAddMode(mode) {
  $$("#add-modes button").forEach((b) => b.classList.toggle("on", b.dataset.mode === mode));
  $$("#view-add .mode").forEach((m) => (m.hidden = m.dataset.mode !== mode));
  $("#draft").hidden = true;
  $("#portion").hidden = true;
  setError($("#add-error"));
  if (mode !== "barcode") stopScan();
}
$("#add-modes").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-mode]");
  if (b) setAddMode(b.dataset.mode);
});

let searchTimer;
$("#food-search").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(searchFoods, 200);
});

async function searchFoods() {
  const foods = await api(`/foods?q=${encodeURIComponent($("#food-search").value)}`);
  $("#food-results").innerHTML = foods.length
    ? foods.map((f) => `
      <li class="clickable" data-food='${esc(JSON.stringify(f))}'>
        <div class="grow"><div class="name">${esc(f.name)}${f.brand ? ` <span class="muted small">${esc(f.brand)}</span>` : ""}</div>
        <div class="sub">per 100 g: ${r0(f.kcal)} kcal · P ${r1(f.protein)} · C ${r1(f.carbs)} · F ${r1(f.fat)}</div></div>
        <button class="x" data-del-food="${f.id}" aria-label="Delete food">🗑</button>
      </li>`).join("")
    : `<li class="muted small">No saved foods yet. Add one by barcode, photo, description or manually.</li>`;
}

$("#food-results").addEventListener("click", async (e) => {
  const del = e.target.closest("[data-del-food]");
  if (del) {
    e.stopPropagation();
    if (confirm("Delete this saved food?")) {
      await api(`/foods/${del.dataset.delFood}`, { method: "DELETE" });
      searchFoods();
    }
    return;
  }
  const li = e.target.closest("[data-food]");
  if (li) openPortion(JSON.parse(li.dataset.food));
});

function showDraft(d, title = "Check the values") {
  const form = $("#draft");
  $("#draft-title").textContent = title;
  $("#draft-source").textContent = { barcode: "Open Food Facts", label_photo: "AI · label", ai_estimate: "AI · estimate", manual: "Manual" }[d.source] || "";
  const notes = [];
  if (d.confidence) notes.push(`Confidence: ${d.confidence}.`);
  if (d.notes) notes.push(d.notes);
  if (d.complete === false) notes.push("Some values are missing in the database; please fill them in.");
  $("#draft-notes").textContent = notes.join(" ");
  for (const k of ["name", "brand", "serving_g", "kcal", "protein", "carbs", "fat", "fiber", "sugar", "barcode", "source"]) {
    form.elements[k].value = d[k] ?? "";
  }
  form.hidden = false;
  $("#portion").hidden = true;
  form.scrollIntoView({ behavior: "smooth", block: "start" });
}

$("#manual-start").addEventListener("click", () => showDraft({ source: "manual" }, "New food (per 100 g)"));

$("#draft").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = Object.fromEntries(new FormData(e.target));
  try {
    const food = await api("/foods", { method: "POST", body });
    e.target.hidden = true;
    openPortion(food);
  } catch (err) {
    setError($("#add-error"), err);
  }
});

function openPortion(food) {
  state.selectedFood = food;
  const form = $("#portion");
  $("#portion-name").textContent = food.name;
  $("#portion-per100").textContent = `${r0(food.kcal)} kcal / 100 g`;
  form.elements.grams.value = food.serving_g || 100;
  fillMealSelects();
  updatePortionPreview();
  form.hidden = false;
  $("#draft").hidden = true;
  form.scrollIntoView({ behavior: "smooth", block: "start" });
}

function updatePortionPreview() {
  const f = state.selectedFood;
  const g = Number($("#portion").elements.grams.value) || 0;
  const k = g / 100;
  $("#portion-preview").textContent = f
    ? `${r0(f.kcal * k)} kcal · P ${r1(f.protein * k)} g · C ${r1(f.carbs * k)} g · F ${r1(f.fat * k)} g`
    : "";
}
$("#portion").elements.grams.addEventListener("input", updatePortionPreview);

$("#portion").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = new FormData(e.target);
  state.addMeal = f.get("meal");
  try {
    await api("/log", {
      method: "POST",
      body: { food_id: state.selectedFood.id, grams: f.get("grams"), meal: f.get("meal"), day: state.day },
    });
    e.target.hidden = true;
    go("today");
  } catch (err) {
    setError($("#add-error"), err);
  }
});

$("#quick-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = { ...Object.fromEntries(new FormData(e.target)), day: state.day };
  try {
    await api("/log", { method: "POST", body });
    e.target.reset();
    go("today");
  } catch (err) {
    setError($("#add-error"), err);
  }
});

// Barcode: live camera via ZXing (lazy-loaded), photo of a barcode, or typed digits.
let zxing = null;
let scanControls = null;

async function loadZXing() {
  if (zxing) return zxing;
  await new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "https://unpkg.com/@zxing/browser@0.1.5/umd/zxing-browser.min.js";
    s.onload = resolve;
    s.onerror = () => reject(new Error("Couldn't load the barcode scanner."));
    document.head.append(s);
  });
  zxing = new window.ZXingBrowser.BrowserMultiFormatReader();
  return zxing;
}

function stopScan() {
  scanControls?.stop();
  scanControls = null;
  $("#scanner").hidden = true;
  $("#scan-start").textContent = "📷 Scan";
}

$("#scan-start").addEventListener("click", async () => {
  if (scanControls) return stopScan();
  setError($("#add-error"));
  if (!navigator.mediaDevices?.getUserMedia) {
    return setError($("#add-error"), new Error("Live camera needs HTTPS. Use 'Photo of barcode' or type the number."));
  }
  try {
    const reader = await loadZXing();
    $("#scanner").hidden = false;
    $("#scan-start").textContent = "■ Stop";
    scanControls = await reader.decodeFromConstraints(
      { video: { facingMode: "environment" } },
      $("#scan-video"),
      (result) => {
        if (result) {
          stopScan();
          lookupBarcode(result.getText());
        }
      }
    );
  } catch (err) {
    stopScan();
    setError($("#add-error"), err);
  }
});

$("#barcode-photo").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  e.target.value = "";
  if (!file) return;
  setError($("#add-error"));
  try {
    const reader = await loadZXing();
    const url = URL.createObjectURL(file);
    const result = await reader.decodeFromImageUrl(url).finally(() => URL.revokeObjectURL(url));
    lookupBarcode(result.getText());
  } catch {
    setError($("#add-error"), new Error("No barcode found in that photo. Try closer, or type the number."));
  }
});

$("#barcode-form").addEventListener("submit", (e) => {
  e.preventDefault();
  lookupBarcode($("#barcode-input").value.trim());
});

async function lookupBarcode(code) {
  $("#barcode-input").value = code;
  setError($("#add-error"));
  busy($("#add-loading"), true);
  try {
    const product = await api(`/foods/barcode/${encodeURIComponent(code)}`);
    if (product.saved) openPortion(product);
    else showDraft(product, "Found it! Check the values");
  } catch (err) {
    setError($("#add-error"), err);
  } finally {
    busy($("#add-loading"), false);
  }
}

// Label photo -> resize in the browser (smaller upload, faster AI) -> AI reads the label.
function resizeImage(file, max = 1568) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const scale = Math.min(1, max / Math.max(img.width, img.height));
      const c = document.createElement("canvas");
      c.width = Math.round(img.width * scale);
      c.height = Math.round(img.height * scale);
      c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
      URL.revokeObjectURL(img.src);
      resolve(c.toDataURL("image/jpeg", 0.85));
    };
    img.onerror = () => reject(new Error("Couldn't read that image."));
    img.src = URL.createObjectURL(file);
  });
}

$("#label-photo").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  e.target.value = "";
  if (!file) return;
  setError($("#add-error"));
  busy($("#add-loading"), true);
  try {
    const dataUrl = await resizeImage(file);
    $("#label-preview").src = dataUrl;
    $("#label-preview").hidden = false;
    const draft = await api("/foods/label", {
      method: "POST",
      body: { image: dataUrl.split(",")[1], media_type: "image/jpeg", hint: $("#label-hint").value },
    });
    showDraft(draft, "Read from the label");
  } catch (err) {
    setError($("#add-error"), err);
  } finally {
    busy($("#add-loading"), false);
  }
});

$("#describe-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const description = $("#describe-input").value.trim();
  if (!description) return;
  setError($("#add-error"));
  busy($("#add-loading"), true);
  try {
    showDraft(await api("/foods/estimate", { method: "POST", body: { description } }), "AI estimate");
  } catch (err) {
    setError($("#add-error"), err);
  } finally {
    busy($("#add-loading"), false);
  }
});

// ---------- recipes ----------

const RECIPE_TAGS = ["saved", "breakfast", "lunch", "dinner", "snack", "low-carb", "vegetarian", "vegan", "meal-prep", "no-cook", "dairy-free"];
const SOURCE_LABEL = { ai: "AI", spoonacular: "Spoonacular", mealdb: "TheMealDB" };
let lastRecipes = [];
let onlineSource = "spoonacular";

function setRecipeMode(mode) {
  $$("#recipe-modes button").forEach((b) => b.classList.toggle("on", b.dataset.rmode === mode));
  $$("#view-recipes .rmode").forEach((m) => (m.hidden = m.dataset.rmode !== mode));
  $("#recipe-list").innerHTML = "";
  setError($("#recipe-error"));
  if (mode === "browse") browseRecipes();
  if (mode === "online") setOnlineSource(onlineSource);
}
$("#recipe-modes").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-rmode]");
  if (b) setRecipeMode(b.dataset.rmode);
});

$("#recipe-tags").innerHTML = RECIPE_TAGS.map((t) => `<button class="chip" data-tag="${t}">${t === "saved" ? "⭐ saved" : t}</button>`).join("");
$("#recipe-tags").addEventListener("click", (e) => {
  const b = e.target.closest("[data-tag]");
  if (!b) return;
  state.recipeTag = state.recipeTag === b.dataset.tag ? null : b.dataset.tag;
  $$("#recipe-tags .chip").forEach((c) => c.classList.toggle("on", c.dataset.tag === state.recipeTag));
  browseRecipes();
});
let recipeTimer;
["#recipe-q", "#recipe-max", "#recipe-minp"].forEach((s) =>
  $(s).addEventListener("input", () => {
    clearTimeout(recipeTimer);
    recipeTimer = setTimeout(browseRecipes, 250);
  })
);

async function browseRecipes() {
  const p = new URLSearchParams({ q: $("#recipe-q").value, max_kcal: $("#recipe-max").value, min_protein: $("#recipe-minp").value });
  if (state.recipeTag) p.set("tag", state.recipeTag);
  renderRecipes(await api(`/recipes?${p}`));
}

function recipeBadge(r) {
  if (r.saved_id) return `<span class="badge">⭐ ${SOURCE_LABEL[r.source] || "Saved"}</span>`;
  if (SOURCE_LABEL[r.source]) return `<span class="badge">${SOURCE_LABEL[r.source]}</span>`;
  return "";
}

function hasMacros(r) {
  return r.kcal !== null && r.kcal !== undefined;
}

function renderRecipes(list) {
  lastRecipes = list;
  $("#recipe-list").innerHTML = list.length
    ? list.map((r, i) => {
      const canSave = !r.saved_id && SOURCE_LABEL[r.source] && hasMacros(r);
      const macros = hasMacros(r)
        ? `<span><b>${r0(r.kcal)}</b> kcal</span><span class="p"><b>${r0(r.protein)}</b> g protein</span><span>C ${r0(r.carbs)} · F ${r0(r.fat)}</span>`
        : `<span class="est">macros unknown</span>`;
      return `
    <article class="card recipe">
      <div class="head" data-toggle="${i}">
        <div class="head-main">
          ${r.image_url ? `<img class="thumb" src="${esc(r.image_url)}" alt="" loading="lazy" referrerpolicy="no-referrer">` : ""}
          <div><h3>${esc(r.title)} ${recipeBadge(r)}</h3>
            <div class="stats">${macros}${r.minutes ? `<span>⏱ ${r.minutes} min</span>` : ""}${r.servings ? `<span>🍽 ${r0(r.servings)}</span>` : ""}</div>
            ${r.macros_estimated && hasMacros(r) ? `<div class="est">≈ macros estimated by AI</div>` : ""}
            ${r.missing ? `<div class="small"><span class="have">✓ ${r.have.map(esc).join(", ") || "—"}</span>${r.missing.length ? ` · <span class="missing">need ${r.missing.map(esc).join(", ")}</span>` : ""}</div>` : ""}
          </div>
        </div>
        <span class="muted">▾</span>
      </div>
      <div class="body" hidden>
        <h4>Ingredients</h4>
        <ul>${r.ingredients.map((g) => `<li>${esc(g.name)} ${g.amount ? `<span class="muted">${esc(g.amount)}</span>` : ""}</li>`).join("")}</ul>
        <h4>Steps</h4>
        <ol>${r.steps.map((s) => `<li>${esc(s)}</li>`).join("")}</ol>
        ${r.source_url ? `<p class="small"><a href="${esc(r.source_url)}" target="_blank" rel="noopener noreferrer">Original recipe ↗</a></p>` : ""}
        <div class="actions">
          ${canSave ? `<button class="btn" data-save="${i}">⭐ Save to my recipes</button>` : ""}
          ${r.saved_id ? `<button class="btn" data-unsave="${i}">Remove from my recipes</button>` : ""}
        </div>
        ${hasMacros(r) ? `
        <form class="row cook" data-cook="${i}">
          <input name="servings" type="number" step="0.25" min="0.25" value="1" style="max-width:90px" aria-label="Servings">
          <select name="meal" class="meal-select" style="max-width:160px"></select>
          <button class="btn primary" type="submit">👩‍🍳 I cooked this (+15 XP)</button>
        </form>` : ""}
      </div>
    </article>`;
    }).join("")
    : `<p class="muted">No recipes match. Try fewer filters, search online${state.me?.ai_enabled ? " or ask the AI" : ""}.</p>`;
  fillMealSelects();
}

$("#recipe-list").addEventListener("click", async (e) => {
  const save = e.target.closest("[data-save]");
  if (save) {
    const r = lastRecipes[Number(save.dataset.save)];
    try {
      const saved = await api("/recipes/saved", { method: "POST", body: { recipe: r } });
      lastRecipes[Number(save.dataset.save)] = { ...r, ...saved };
      toast(`⭐ Saved ${r.title}`);
      renderRecipes(lastRecipes);
    } catch (err) {
      toast(err.message, true);
    }
    return;
  }
  const unsave = e.target.closest("[data-unsave]");
  if (unsave) {
    const r = lastRecipes[Number(unsave.dataset.unsave)];
    if (!confirm(`Remove "${r.title}" from your recipes?`)) return;
    await api(`/recipes/saved/${r.saved_id}`, { method: "DELETE" });
    lastRecipes[Number(unsave.dataset.unsave)] = { ...r, saved_id: null, id: null };
    renderRecipes(lastRecipes);
    return;
  }
  const head = e.target.closest("[data-toggle]");
  if (head) {
    const body = head.parentElement.querySelector(".body");
    body.hidden = !body.hidden;
  }
});
$("#recipe-list").addEventListener("submit", async (e) => {
  e.preventDefault();
  const r = lastRecipes[Number(e.target.dataset.cook)];
  const f = new FormData(e.target);
  const body = { servings: f.get("servings"), meal: f.get("meal"), day: state.day };
  if (r.saved_id || r.source === "built_in") body.recipe_id = r.id;
  else body.recipe = r;
  try {
    await api("/recipes/cook", { method: "POST", body });
    toast(`Logged ${r.title}`);
  } catch (err) {
    toast(err.message, true);
  }
});

$("#pantry-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  setError($("#recipe-error"));
  try {
    const res = await api("/recipes/pantry", { method: "POST", body: { ingredients: $("#pantry-input").value } });
    renderRecipes(res.recipes);
  } catch (err) {
    setError($("#recipe-error"), err);
  }
});

// Online search (Spoonacular / TheMealDB)
function setOnlineSource(src) {
  onlineSource = src;
  $$("#online-source button").forEach((b) => b.classList.toggle("on", b.dataset.source === src));
  const me = state.me || {};
  $("#online-hint").textContent = src === "spoonacular"
    ? (me.spoonacular_enabled ? "Real recipes with exact macros per serving." : "Not set up: add SPOONACULAR_API_KEY on the server (free key at spoonacular.com/food-api).")
    : (me.ai_enabled ? "Free recipe database. It has no nutrition data, so AI estimates the macros." : "Free recipe database without nutrition data. Enable AI to estimate macros.");
}
$("#online-source").addEventListener("click", (e) => {
  const b = e.target.closest("[data-source]");
  if (b) setOnlineSource(b.dataset.source);
});

async function onlineRecipes(params) {
  setError($("#recipe-error"));
  busy($("#recipe-loading"), true);
  $("#recipe-list").innerHTML = "";
  try {
    const p = new URLSearchParams({ source: onlineSource, ...params });
    const res = await api(`/recipes/online?${p}`);
    if (res.note) toast(res.note);
    renderRecipes(res.recipes);
  } catch (err) {
    setError($("#recipe-error"), err);
  } finally {
    busy($("#recipe-loading"), false);
  }
}
$("#online-form").addEventListener("submit", (e) => {
  e.preventDefault();
  onlineRecipes({
    q: $("#online-q").value, ingredients: $("#online-ingredients").value,
    max_kcal: $("#online-max").value, min_protein: $("#online-minp").value,
  });
});
$("#pantry-online").addEventListener("click", () => {
  const ingredients = $("#pantry-input").value;
  setRecipeMode("online");
  $("#online-ingredients").value = ingredients;
  onlineRecipes({ ingredients, min_protein: $("#online-minp").value });
});

async function aiRecipes(body) {
  setError($("#recipe-error"));
  busy($("#recipe-loading"), true);
  $("#recipe-list").innerHTML = "";
  try {
    const res = await api("/recipes/ai", { method: "POST", body: { ...body, day: state.day } });
    if (res.budget) toast(`Aiming for ~${res.budget.kcal} kcal, ${res.budget.protein} g protein`);
    renderRecipes(res.recipes);
  } catch (err) {
    setError($("#recipe-error"), err);
  } finally {
    busy($("#recipe-loading"), false);
  }
}
$("#pantry-ai").addEventListener("click", () => aiRecipes({ ingredients: $("#pantry-input").value, use_remaining: true }));
$("#ai-recipe-form").addEventListener("submit", (e) => {
  e.preventDefault();
  aiRecipes({ ingredients: $("#ai-ingredients").value, preferences: $("#ai-prefs").value, use_remaining: $("#ai-remaining").checked });
});

// ---------- me ----------

async function loadMe() {
  const [p, game, weights] = await Promise.all([api("/profile"), refreshGame(), api("/weight")]);
  const form = $("#profile-form");
  if (p.profile) for (const k of ["sex", "birth_year", "height_cm", "weight_kg", "job_activity", "goal"]) form.elements[k].value = p.profile[k];
  renderTargets(p.targets);
  renderSports(p.sports);
  renderWeight(weights);

  $("#badges").innerHTML = game.badges.map((b) => `
    <div class="badge-tile ${b.earned_at ? "" : "locked"}" title="${esc(b.description)}">
      <div class="ic">${b.icon}</div><div class="bn">${esc(b.name)}</div><div class="bd">${esc(b.description)}</div>
    </div>`).join("");
  $("#recent-xp").innerHTML = game.recent.length
    ? game.recent.map((x) => `<li><span>${esc(x.label)}</span><b>+${x.points}</b></li>`).join("")
    : `<li class="muted">Log food to start earning XP.</li>`;
}

function renderTargets(t) {
  $("#targets-card").hidden = !t;
  if (!t) return;
  $("#targets").innerHTML = [["kcal", "kcal"], ["protein", "protein g"], ["carbs", "carbs g"], ["fat", "fat g"]]
    .map(([k, l]) => `<div><b>${t[k]}</b><span>${l}</span></div>`).join("");
  $("#targets-explain").textContent =
    `Resting burn ${t.bmr} kcal · with job & training ≈ ${t.tdee} kcal/day (sports add ~${t.exercise_kcal_per_day}). BMI ${t.bmi}. ` +
    `These are estimates; adjust if your weight trend says otherwise.`;
}

function renderSports(sports) {
  $("#sports").innerHTML = sports.length
    ? sports.map((s) => `<li><div class="grow"><div class="name">${esc(s.name)}</div>
        <div class="sub">${s.sessions_per_week}×/week · ${s.minutes_per_session} min · ${s.intensity}</div></div>
        <button class="x" data-del-sport="${s.id}" aria-label="Remove">✕</button></li>`).join("")
    : `<li class="muted small">No sports yet.</li>`;
}

function renderWeight(rows) {
  const svg = $("#weight-chart");
  if (rows.length < 2) {
    svg.innerHTML = `<text x="150" y="45" text-anchor="middle" fill="currentColor" opacity=".5" font-size="12">Log your weight on a few days to see a trend</text>`;
    return;
  }
  const ws = rows.map((r) => r.weight_kg);
  const lo = Math.min(...ws) - 0.5, hi = Math.max(...ws) + 0.5;
  const pts = rows.map((r, i) => `${(i / (rows.length - 1)) * 300},${80 - ((r.weight_kg - lo) / (hi - lo)) * 76 - 2}`).join(" ");
  svg.innerHTML = `<polyline points="${pts}"/>`;
  svg.setAttribute("aria-label", `Weight trend: ${ws[0]} kg to ${ws.at(-1)} kg`);
}

$("#profile-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const p = await api("/profile", { method: "PUT", body: Object.fromEntries(new FormData(e.target)) });
    renderTargets(p.targets);
    toast("Profile saved");
    loadMe();
  } catch (err) {
    toast(err.message, true);
  }
});

$("#sport-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/sports", { method: "POST", body: Object.fromEntries(new FormData(e.target)) });
    e.target.elements.name.value = "";
    loadMe();
  } catch (err) {
    toast(err.message, true);
  }
});

$("#sports").addEventListener("click", async (e) => {
  const b = e.target.closest("[data-del-sport]");
  if (b) {
    await api(`/sports/${b.dataset.delSport}`, { method: "DELETE" });
    loadMe();
  }
});

$("#weight-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/weight", { method: "POST", body: { weight_kg: e.target.elements.weight_kg.value, day: localDay(new Date()) } });
    e.target.reset();
    loadMe();
  } catch (err) {
    toast(err.message, true);
  }
});

// ---------- boot ----------

async function boot() {
  try {
    state.me = await api("/me");
  } catch {
    return showAuth();
  }
  $("#view-auth").hidden = true;
  $("#shell").hidden = false;
  document.body.classList.toggle("no-ai", !state.me.ai_enabled);
  $$("[data-mode=photo], [data-mode=describe], [data-rmode=ai], .ai-only").forEach((el) => {
    if (!state.me.ai_enabled && el.tagName === "BUTTON") {
      el.disabled = true;
      el.title = "Set ANTHROPIC_API_KEY on the server to enable AI features";
    }
  });
  go(state.me.has_profile ? "today" : "me");
}

if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
boot();
