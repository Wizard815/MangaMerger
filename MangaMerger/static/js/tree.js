let selectedFolder = null;
let lastChecked = null;

async function loadTree() {
  const treeEl = document.getElementById("tree");
  treeEl.innerHTML = "⏳ Loading...";
  try {
    const res = await fetch("/api/tree");
    const data = await res.json();
    treeEl.innerHTML = "";
    if (data.error) return treeEl.innerHTML = `<li>${data.error}</li>`;
    buildTreeDom(data, treeEl);
  } catch (err) {
    treeEl.innerHTML = `<li>Error: ${err}</li>`;
  }
}

function buildTreeDom(nodes, container) {
  nodes.forEach(node => {
    const li = document.createElement("li");
    li.classList.add("tree-item");

    const arrow = document.createElement("span");
    arrow.textContent = node.children.length ? "▶" : "•";
    arrow.classList.add("arrow");

    const name = document.createElement("span");
    const countText = node.count ? ` (${node.count})` : "";
    name.textContent = " " + node.name + (node.count ? ` (${node.count})` : "");
    name.dataset.count = node.count ? `${node.count} chapters` : "";
    name.classList.add("folder-name");

    arrow.onclick = () => {
      if (arrow.textContent === "▶") {
        arrow.textContent = "▼";
        if (!li.querySelector("ul")) {
          const ul = document.createElement("ul");
          ul.classList.add("nested");
          buildTreeDom(node.children, ul);
          li.appendChild(ul);
        } else {
          li.querySelector("ul").style.display = "block";
        }
      } else {
        arrow.textContent = "▶";
        const sub = li.querySelector("ul");
        if (sub) sub.style.display = "none";
      }
    };

    name.onclick = () => showFolder(node.path);

    li.appendChild(arrow);
    li.appendChild(name);
    container.appendChild(li);
  });
}

async function showFolder(folderPath) {
  selectedFolder = { name: folderPath };
  const list = document.getElementById("chapter-list");
  const combinePanel = document.getElementById("combine-panel");
  list.innerHTML = "⏳ Loading chapters...";

  try {
    const res = await fetch(`/api/folder?path=${encodeURIComponent(folderPath)}`);
    const data = await res.json();

    list.innerHTML = "";
    if (!data.chapters || data.chapters.length === 0) {
      list.innerHTML = "<li>No chapters found.</li>";
      combinePanel.classList.add("hidden");
      return;
    }

    data.chapters.forEach(ch => {
      const li = document.createElement("li");
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.classList.add("chapter-checkbox");
      const label = document.createElement("label");
      label.textContent = ch;
      li.appendChild(cb);
      li.appendChild(label);
      list.appendChild(li);
    });

    combinePanel.classList.remove("hidden");
    setupCheckboxLogic();
    setupCombineButtons();
  } catch (err) {
    list.innerHTML = `<li>Error: ${err}</li>`;
  }
}

function setupCheckboxLogic() {
  lastChecked = null;
  const boxes = Array.from(document.querySelectorAll(".chapter-checkbox"));
  boxes.forEach(cb => {
    cb.addEventListener("click", (e) => {
      if (e.shiftKey && lastChecked) {
        const start = boxes.indexOf(cb);
        const end = boxes.indexOf(lastChecked);
        const [min, max] = [Math.min(start, end), Math.max(start, end)];
        for (let i = min; i <= max; i++) boxes[i].checked = lastChecked.checked;
      }
      lastChecked = cb;
    });
  });
}

function setupCombineButtons() {
  const pdfBtn = document.getElementById("btn-pdf");
  const cbzBtn = document.getElementById("btn-cbz");buildTreeDom
  const nameInput = document.getElementById("volume-name");

  async function handleCombine(type) {
    const boxes = Array.from(document.querySelectorAll(".chapter-checkbox"));
    const selected = boxes.map((b, i) => (b.checked ? b.nextSibling.textContent : null)).filter(Boolean);
    const name = nameInput.value.trim() || "Volume_01";
    if (!selected.length) return alert("⚠️ No chapters selected.");

    const payload = { folder: selectedFolder.name, selected, name, type };
    const banner = document.getElementById("status-banner");
    const statusText = document.getElementById("status-text");
    banner.classList.remove("hidden");
    statusText.textContent = `Combining ${selected.length} chapters as ${type.toUpperCase()}...`;

    try {
      const res = await fetch("/api/combine", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
      });
      const result = await res.json();
      banner.classList.add("hidden");
      if (result.success) alert(`✅ ${name}.${type.toUpperCase()} created!\n\n${result.path}`);
      else alert(`❌ Combine failed: ${result.error || "Unknown"}`);
    } catch (err) {
      banner.classList.add("hidden");
      alert(`❌ Combine failed: ${err.message}`);
    }
  }

  pdfBtn.onclick = () => handleCombine("pdf");
  cbzBtn.onclick = () => handleCombine("cbz");
}

window.addEventListener("DOMContentLoaded", loadTree);
