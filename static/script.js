// --- VARIABLES GLOBALES Y CONFIGURACIÓN ---
let masterFlashcardsData = []; // Todas las tarjetas, nunca cambia
let filteredFlashcardsData = []; // Tarjetas que no han sido aprendidas
let currentIndex = 0; // Índice para la lista FILTRADA
const API_URL = 'http://127.0.0.1:8000';
let audioPlayer = new Audio();
let isAudioPlaying = false;
let awaitingDeleteConfirmation = false;
let deleteConfirmationTimeoutId = null;

// Offset para ajustar la sincronización del resaltado (en segundos)
const SYNC_OFFSET = 0.15;

// --- ELEMENTOS DEL DOM ---
let cardElement, loadingGif, deleteImageButton, nextButton, prevButton, messageElement, cardCounterElement, flashcardContainer;

// --- FUNCIÓN AUXILIAR PARA PAUSAR ---
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// --- FUNCIONES DE MANEJO DE LA INTERFAZ ---
function toggleNavigation(disabled) {
    if (nextButton) nextButton.disabled = disabled;
    if (prevButton) prevButton.disabled = disabled;
    if (deleteImageButton) {
        deleteImageButton.style.pointerEvents = disabled ? 'none' : 'auto';
        deleteImageButton.style.opacity = disabled ? 0.5 : 1;
    }
}

function showAppMessage(text, isError = false) {
    if (messageElement) {
        messageElement.textContent = text;
        messageElement.style.color = isError ? '#D32F2F' : '#333';
    }
    if (isError) {
        console.error("APP MESSAGE:", text);
    }
}

// --- LÓGICA DE AUDIO Y RESALTADO (CON CAPA DE CARGA) ---
async function playAudioFromApi(text, itemElement = null) {
    if (isAudioPlaying) {
        audioPlayer.pause();
    }
    isAudioPlaying = false;
    audioPlayer.ontimeupdate = null;

    document.querySelectorAll('.highlighted-word').forEach(el => el.classList.remove('highlighted-word'));
    document.querySelectorAll('.active-example-line').forEach(el => el.classList.remove('active-example-line'));

    toggleNavigation(true);
    if (itemElement) itemElement.classList.add('active-example-line');

    if (itemElement && itemElement.tagName === 'LI') {
        itemElement.classList.add('loading-audio');
    } else {
        showAppMessage("⏳ Cargando audio...", false);
    }

    try {
        const voice_name = "Aoede";
        const model_name = "gemini-2.5-pro-tts";

        const response = await fetch(`${API_URL}/api/synthesize-speech`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text,
                voice_name,
                model_name,
                category: filteredFlashcardsData[currentIndex].category || "phrasal_verbs", // Fallback seguro
                deck: filteredFlashcardsData[currentIndex].deck_name || "unknown",
                verb_name: filteredFlashcardsData[currentIndex].name,
                tone: "Read this like a news anchor"
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Error en la API de voz.');
        }

        // --- CAMBIO CLAVE: Manejar respuesta JSON con URL en lugar de Blob ---
        const data = await response.json();

        if (data.success && data.audio_url) {
            // Convertir URL absoluta de GCS a ruta relativa para usar el redirect del backend
            // GCS URL: https://storage.googleapis.com/bucket/card_audio/category/deck/file.mp3
            // Ruta relativa: /card_audio/category/deck/file.mp3

            let audioSrc = data.audio_url;
            if (audioSrc.includes('/card_audio/')) {
                const relativePath = audioSrc.split('/card_audio/')[1];
                audioSrc = `${API_URL}/card_audio/${relativePath}`;
            }

            audioPlayer.src = audioSrc;

            if (itemElement) {
                const textContainer = itemElement.id === 'name' ? itemElement : itemElement.querySelector('div');
                const wordSpans = textContainer ? Array.from(textContainer.children).filter(el => el.tagName === 'SPAN') : [];
                let lastHighlightedIndex = -1;

                audioPlayer.onloadedmetadata = () => {
                    const audioDuration = audioPlayer.duration;
                    if (!audioDuration || wordSpans.length === 0) return;
                    const timePerWord = audioDuration / wordSpans.length;

                    audioPlayer.ontimeupdate = () => {
                        const currentTime = audioPlayer.currentTime + SYNC_OFFSET;
                        const currentWordIndex = Math.floor(currentTime / timePerWord);

                        if (currentWordIndex !== lastHighlightedIndex) {
                            if (lastHighlightedIndex >= 0 && wordSpans[lastHighlightedIndex]) {
                                wordSpans[lastHighlightedIndex].classList.remove('highlighted-word');
                            }
                            if (currentWordIndex >= 0 && currentWordIndex < wordSpans.length) {
                                wordSpans[currentWordIndex].classList.add('highlighted-word');
                            }
                            lastHighlightedIndex = currentWordIndex;
                        }
                    };
                };
            }

            await audioPlayer.play();
            isAudioPlaying = true;
            showAppMessage("▶️ Reproduciendo...");

            audioPlayer.onended = () => {
                if (itemElement) itemElement.classList.remove('active-example-line');
                document.querySelectorAll('.highlighted-word').forEach(el => el.classList.remove('highlighted-word'));
                showAppMessage("Audio finalizado.");
                toggleNavigation(false);
                isAudioPlaying = false;
            };
        } else {
            throw new Error("La respuesta de audio no contiene una URL válida.");
        }

    } catch (error) {
        showAppMessage(`❌ Error de TTS: ${error.message}`, true);
        toggleNavigation(false);
    } finally {
        if (itemElement && itemElement.tagName === 'LI') {
            itemElement.classList.remove('loading-audio');
        }
    }
}

function playPhonetic(event) {
    event.stopPropagation();
    const nameElement = document.getElementById('name');
    playAudioFromApi(filteredFlashcardsData[currentIndex].name, nameElement);
}

function playSingleExample(event, index) {
    event.stopPropagation();
    const text = filteredFlashcardsData[currentIndex].definitions[index].usage_example;
    const itemElement = document.getElementById(`example-item-${index}`);
    playAudioFromApi(text, itemElement);
}

// --- LÓGICA DE LA TARJETA ---
function renderFrontExamples(card) {
    const container = document.getElementById('allExamplesContainer');
    container.innerHTML = '';
    const list = document.createElement('ul');
    card.definitions.forEach((def, index) => {
        const item = document.createElement('li');
        item.id = `example-item-${index}`;

        const playButton = document.createElement('button');
        playButton.innerHTML = '🔊';
        playButton.setAttribute('onclick', `playSingleExample(event, ${index})`);

        const textContainer = document.createElement('div');
        textContainer.classList.add('blurred-text');

        textContainer.addEventListener('click', (event) => {
            event.stopPropagation();
            event.currentTarget.classList.remove('blurred-text');
        });

        def.usage_example.trim().split(/\s+/).forEach(word => {
            const span = document.createElement('span');
            span.textContent = word + ' ';
            textContainer.appendChild(span);
        });

        item.append(playButton, textContainer);
        list.appendChild(item);
    });
    container.appendChild(list);
}

function renderCardName(card) {
    const nameElement = document.getElementById('name');
    nameElement.innerHTML = '';

    card.name.trim().split(/\s+/).forEach(word => {
        const span = document.createElement('span');
        span.classList.add('card-name-word');
        span.textContent = word + ' ';
        nameElement.appendChild(span);
    });
}

function renderBackCard(card) {
    const container = document.getElementById('exampleBackContainer');
    container.innerHTML = '';

    card.definitions.forEach(def => {
        const definitionBlock = document.createElement('div');
        definitionBlock.className = 'definition-block-back';

        const verbRegex = new RegExp(`\\b(${card.name})\\b`, 'i');
        const highlightedExample = def.usage_example.replace(verbRegex, `<strong>$1</strong>`);

        let alternativeExampleHTML = '';
        if (card.is_phrasal_verb && def.alternative_example) {
            alternativeExampleHTML = `<p class="alternative-example"><em>Alternativa:</em> "${def.alternative_example}"</p>`;
        }

        definitionBlock.innerHTML = `
            <p class="meaning-sentence">
                <span class="phrasal-verb-back">${card.name}</span> significa <strong class="meaning-back">${def.meaning}</strong>
            </p>
            <p class="usage-example-en">"${highlightedExample}"</p>
            ${alternativeExampleHTML}
            <p class="usage-example-es">${def.usage_example_es}</p>
        `;
        container.appendChild(definitionBlock);
    });
}

async function loadCard(index, autoPlay = false) {
    if (filteredFlashcardsData.length === 0) {
        displayCompletionMessage();
        return;
    }
    if (isAudioPlaying) audioPlayer.pause();
    awaitingDeleteConfirmation = false;
    clearTimeout(deleteConfirmationTimeoutId);

    currentIndex = index;
    const card = filteredFlashcardsData[index];

    cardElement.classList.remove('flipped', 'loading');
    toggleNavigation(true);
    showAppMessage("Cargando tarjeta...");
    updateCardCounter();

    renderCardName(card);
    document.getElementById('phonetic').textContent = card.phonetic;
    renderFrontExamples(card);
    renderBackCard(card);

    const img = document.getElementById('image');
    img.src = '';
    img.style.opacity = '0';
    deleteImageButton.style.display = 'none';
    loadingGif.style.display = 'block';

    if (card.imagePath) {
        const imageFullPath = `${API_URL}${card.imagePath}`;
        const tempImg = new Image();
        tempImg.src = imageFullPath;

        tempImg.onload = () => {
            img.src = imageFullPath;
            img.style.opacity = '1';
            deleteImageButton.style.display = 'flex';
            loadingGif.style.display = 'none';
            showAppMessage("Tarjeta lista.");
            toggleNavigation(false);
            if (autoPlay) {
                const nameElement = document.getElementById('name');
                playAudioFromApi(card.name, nameElement);
            }
        };
        tempImg.onerror = () => generateAndLoadImage(card);
    } else {
        generateAndLoadImage(card);
    }
}

function generateAndLoadImage(card) {
    const img = document.getElementById('image');
    cardElement.classList.add('loading');
    showAppMessage("⏳ Generando imagen de IA...");

    const def = card.definitions[0];
    const prompt = `Generate a single, clear, educational illustration for the phrasal verb "${card.name}" meaning "${def.meaning}". Context: "${def.usage_example}". Style: Photorealistic, bright, daylight, professional photography aesthetic. No text or labels.`;

    fetch(`${API_URL}/api/generate-image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ index: card.id, def_index: 0, prompt })
    })
        .then(res => res.ok ? res.json() : Promise.reject(res.json()))
        .then(data => {
            const newImagePath = `${API_URL}${data.path}?t=${Date.now()}`;
            const tempImg = new Image();
            tempImg.src = newImagePath;

            filteredFlashcardsData[currentIndex].imagePath = data.path;

            tempImg.onload = () => {
                img.src = newImagePath;
                img.style.opacity = '1';
                deleteImageButton.style.display = 'flex';
                loadingGif.style.display = 'none';
                cardElement.classList.remove('loading');
                showAppMessage("¡Imagen generada!");
                toggleNavigation(false);
            };
        })
        .catch(async (errorPromise) => {
            const error = await errorPromise.catch(e => ({ detail: "Error de red o JSON inválido." }));
            showAppMessage(`❌ Error de IA: ${error.detail}`, true);
            loadingGif.style.display = 'none';
            toggleNavigation(false);
            cardElement.classList.remove('loading');
        });
}

async function deleteImage(event) {
    event.stopPropagation();
    if (awaitingDeleteConfirmation) {
        clearTimeout(deleteConfirmationTimeoutId);
        awaitingDeleteConfirmation = false;
        showAppMessage("🗑️ Eliminando y regenerando...");
        toggleNavigation(true);
        deleteImageButton.style.display = 'none';

        try {
            const cardId = filteredFlashcardsData[currentIndex].id;
            const response = await fetch(`${API_URL}/api/delete-image`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ index: cardId, def_index: 0 })
            });
            if (!response.ok) throw new Error('No se pudo eliminar la imagen.');

            filteredFlashcardsData[currentIndex].imagePath = null;
            loadCard(currentIndex, true);
        } catch (error) {
            showAppMessage(`❌ Error: ${error.message}`, true);
            toggleNavigation(false);
        }
    } else {
        awaitingDeleteConfirmation = true;
        showAppMessage("⚠️ Haz clic de nuevo en 🗑️ para confirmar.", true);
        deleteConfirmationTimeoutId = setTimeout(() => {
            if (awaitingDeleteConfirmation) {
                awaitingDeleteConfirmation = false;
                showAppMessage("Confirmación cancelada.");
            }
        }, 5000);
    }
}

// --- NUEVAS FUNCIONES PARA GESTIONAR ESTADO ---
function displayCompletionMessage() {
    flashcardContainer.innerHTML = `<div class="all-done-message">¡Felicidades! 🎉<br>Has aprendido todas las tarjetas.</div>`;
    if (nextButton) nextButton.style.display = 'none';
    if (prevButton) prevButton.style.display = 'none';
    if (cardCounterElement) cardCounterElement.textContent = "¡Completado!";
}

function updateCardCounter() {
    if (cardCounterElement) {
        if (filteredFlashcardsData.length > 0) {
            //========= AQUÍ ESTÁ EL CAMBIO =========
            cardCounterElement.textContent = `${currentIndex + 1} / ${filteredFlashcardsData.length}`;
        } else {
            cardCounterElement.textContent = "No hay tarjetas para mostrar.";
        }
    }
}

async function markAsLearned(event) {
    event.stopPropagation();
    if (filteredFlashcardsData.length === 0) return;

    toggleNavigation(true);
    showAppMessage("✅ Marcando como aprendida...");

    const currentCard = filteredFlashcardsData[currentIndex];
    const masterIndex = currentCard.id;

    try {
        const response = await fetch(`${API_URL}/api/update-status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ index: masterIndex, learned: true })
        });

        if (!response.ok) {
            throw new Error('Error al actualizar el estado en el servidor.');
        }

        masterFlashcardsData[masterIndex].learned = true;
        filteredFlashcardsData = masterFlashcardsData.filter(card => !card.learned);

        let nextIndex = currentIndex;
        if (nextIndex >= filteredFlashcardsData.length) {
            nextIndex = filteredFlashcardsData.length - 1;
        }

        if (filteredFlashcardsData.length > 0) {
            loadCard(Math.max(0, nextIndex), true);
        } else {
            displayCompletionMessage();
        }

    } catch (error) {
        showAppMessage(`❌ Error: ${error.message}`, true);
        toggleNavigation(false);
    }
}

async function resetAllCards() {
    const isConfirmed = confirm("¿Estás seguro de que quieres resetear el progreso de TODAS las tarjetas?");
    if (isConfirmed) {
        showAppMessage("🔄 Reseteando todas las tarjetas...");
        try {
            const response = await fetch(`${API_URL}/api/reset-all`, {
                method: 'POST'
            });
            if (!response.ok) throw new Error("No se pudo resetear el progreso.");

            showAppMessage("¡Progreso reseteado! Recargando...");
            await sleep(1500);
            location.reload();
        } catch (error) {
            showAppMessage(`❌ Error: ${error.message}`, true);
        }
    }
}

// --- NAVEGACIÓN Y EVENTOS ---
function nextCard() {
    if (filteredFlashcardsData.length > 0) {
        loadCard((currentIndex + 1) % filteredFlashcardsData.length, true);
    }
}

function prevCard() {
    if (filteredFlashcardsData.length > 0) {
        loadCard((currentIndex - 1 + filteredFlashcardsData.length) % filteredFlashcardsData.length, true);
    }
}

function flipCard() {
    if (isAudioPlaying || cardElement.classList.contains('loading')) return;
    cardElement.classList.toggle('flipped');
}

// --- INICIO DE LA APLICACIÓN ---
async function loadData() {
    cardElement = document.getElementById('flashcard');
    loadingGif = document.getElementById('loadingSpinner'); // Reutilizamos la variable pero apuntamos al nuevo elemento
    deleteImageButton = document.getElementById('deleteImageButton');
    nextButton = document.getElementById('nextCardBtn');
    prevButton = document.getElementById('prevCardBtn');
    messageElement = document.getElementById('message');
    cardCounterElement = document.getElementById('cardCounter');
    flashcardContainer = document.querySelector('.flashcard-container');

    try {
        const response = await fetch(`${API_URL}/api/flashcards-data`);
        if (!response.ok) throw new Error('No se pudo cargar los datos desde la API.');
        const data = await response.json();

        masterFlashcardsData = data.map((card, index) => ({ ...card, id: index }));
        filteredFlashcardsData = masterFlashcardsData.filter(card => !card.learned);

        if (filteredFlashcardsData.length > 0) {
            loadCard(currentIndex, false);
        } else {
            displayCompletionMessage();
        }

        const modal = document.getElementById("ipaModal");
        const btn = document.getElementById("ipaChartBtn");
        const span = document.getElementsByClassName("close-button")[0];

        btn.onclick = function (event) {
            event.stopPropagation();
            modal.style.display = "block";
        }
        span.onclick = function () {
            modal.style.display = "none";
        }
        window.onclick = function (event) {
            if (event.target == modal) {
                modal.style.display = "none";
            }
        }

        function speakIPA(buttonElement) {
            const symbol = buttonElement.textContent;
            const fileName = symbol.replace(':', '-');
            const audio = new Audio(`/static/audio/${fileName}.mp4`);

            audio.play().catch(error => {
                console.error(`Error al reproducir ${fileName}.mp4:`, error);
                showAppMessage(`❌ Audio para '${symbol}' no encontrado.`, true);
            });
        }

        document.querySelectorAll(".ipa-btn").forEach(ipaBtn => {
            ipaBtn.addEventListener("click", () => speakIPA(ipaBtn));
        });

    } catch (error) {
        showAppMessage(`❌ Error fatal: ${error.message}`, true);
        console.error(error);
    }
}

document.addEventListener('DOMContentLoaded', loadData);