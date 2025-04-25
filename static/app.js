const form           = document.getElementById("ttsForm");
const btnGenerate    = document.getElementById("generateButton");
const spinner        = document.getElementById("loadingSpinner");
const statusRegion   = document.getElementById("status");
const resultDiv      = document.getElementById("result");
const audioPlayer    = document.getElementById("audioPlayer");
const downloadButton = document.getElementById("downloadButton");
const speedInput     = document.getElementById("speed");
const speedValue     = document.getElementById("speedValue");

// update label on slider move
speedInput.addEventListener("input", () => {
  speedValue.textContent = parseFloat(speedInput.value).toFixed(1);
});

form.addEventListener("submit", async e => {
  e.preventDefault();
  resultDiv.classList.add("d-none");
  statusRegion.textContent = "Envoi de la requête…";
  btnGenerate.disabled = true;
  spinner.classList.remove("d-none");

  const payload = {
    text:         document.getElementById("text").value.trim(),
    voice:        document.getElementById("voice").value,
    instructions: document.getElementById("instructions").value.trim(),
    speed: parseFloat(speedInput.value),
    pause: parseFloat(document.getElementById("pause").value)
  };

  try {
    const response = await fetch("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.error || JSON.stringify(err));
    }

    statusRegion.textContent = "Réception de l'audio…";

    const blob = await response.blob();
    const url  = URL.createObjectURL(blob);

    // preview
    audioPlayer.src = url;
    // enable download
    downloadButton.onclick = () => {
      const a = document.createElement("a");
      a.href = url;
      a.download = "tts.mp3";
      document.body.append(a);
      a.click();
      a.remove();
    };

    resultDiv.classList.remove("d-none");
    statusRegion.textContent = "Synthèse terminée.";

  } catch (err) {
    console.error(err);
    alert("Erreur : " + err.message);
    statusRegion.textContent = "Une erreur est survenue.";
  } finally {
    btnGenerate.disabled = false;
    spinner.classList.add("d-none");
  }
});
