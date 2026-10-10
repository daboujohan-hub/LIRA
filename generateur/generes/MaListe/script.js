let taches = [];

function ajouterTache() {
  const input = document.getElementById("nouvelle-tache");
  const texte = input.value.trim();
  if (!texte) return;
  taches.push({ texte, fait: false });
  input.value = "";
  afficherTaches();
}

function basculerTache(index) {
  taches[index].fait = !taches[index].fait;
  afficherTaches();
}

function supprimerTache(index) {
  taches.splice(index, 1);
  afficherTaches();
}

function afficherTaches() {
  const liste = document.getElementById("liste-taches");
  liste.innerHTML = "";
  taches.forEach((tache, index) => {
    const li = document.createElement("li");
    if (tache.fait) li.classList.add("fait");
    li.innerHTML = `
      <span onclick="basculerTache(${index})">${tache.texte}</span>
      <button onclick="supprimerTache(${index})">✕</button>
    `;
    liste.appendChild(li);
  });
}
