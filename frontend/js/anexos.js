// js/anexos.js - Gerenciamento unificado de múltiplos anexos e Copy & Paste

const arquivosAnexados = new DataTransfer();
let inputAnexoIdGlobal = 'anexo'; // padrão para novo chamado

function inicializarGerenciadorAnexos(inputId) {
    inputAnexoIdGlobal = inputId;
    const anexoInput = document.getElementById(inputId);

    if (anexoInput) {
        anexoInput.addEventListener('change', (e) => {
            for (let file of e.target.files) {
                arquivosAnexados.items.add(file);
            }
            e.target.files = arquivosAnexados.files;
            atualizarListaAnexosUI();
        });
    }

    document.addEventListener('paste', (e) => {
        // Se estiver no detalhe, só cola se a aba do técnico estiver visível
        const cardTec = document.getElementById('cardAcoesTecnico');
        if (cardTec && cardTec.style.display === 'none') return;

        let item_adicionado = false;
        if (e.clipboardData && e.clipboardData.files.length > 0) {
            for (let file of e.clipboardData.files) {
                arquivosAnexados.items.add(file);
                item_adicionado = true;
            }
        }
        if (item_adicionado) {
            const input = document.getElementById(inputAnexoIdGlobal);
            if (input) input.files = arquivosAnexados.files;
            atualizarListaAnexosUI();
        }
    });
}

function atualizarListaAnexosUI() {
    const container = document.getElementById('listaAnexosUI');
    if (!container) return;
    
    container.innerHTML = '';
    Array.from(arquivosAnexados.files).forEach((file, index) => {
        const chip = document.createElement('div');
        chip.className = 'anexo-chip';
        chip.innerHTML = `
            <div id="preview-${index}" style="display: flex; align-items: center; justify-content: center; width: 24px; height: 24px;">
                <span class="material-symbols-outlined" style="font-size: 16px;">description</span>
            </div>
            ${file.name}
            <button type="button" class="anexo-chip-remover" onclick="removerAnexo(${index})">
                <span class="material-symbols-outlined" style="font-size: 16px;">close</span>
            </button>
        `;
        container.appendChild(chip);

        if (file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = function(e) {
                const previewDiv = document.getElementById(`preview-${index}`);
                if (previewDiv) {
                    previewDiv.innerHTML = `<img src="${e.target.result}" style="width: 24px; height: 24px; object-fit: cover; border-radius: 4px;">`;
                }
            };
            reader.readAsDataURL(file);
        }
    });
}

function removerAnexo(index) {
    const dt = new DataTransfer();
    const files = Array.from(arquivosAnexados.files);
    for (let i = 0; i < files.length; i++) {
        if (i !== index) dt.items.add(files[i]);
    }
    arquivosAnexados.items.clear();
    for (let file of dt.files) { arquivosAnexados.items.add(file); }
    const input = document.getElementById(inputAnexoIdGlobal);
    if (input) input.files = arquivosAnexados.files;
    atualizarListaAnexosUI();
}
