/*
 * dashboard.js
 * ------------
 * Desenha os gráficos do dashboard do vendedor com Chart.js.
 * Os dados chegam da view via json_script (JSON seguro dentro da página):
 * o Django continua sendo o dono dos dados, o JavaScript só desenha.
 */
(function () {
    function lerDados(id) {
        const el = document.getElementById(id);
        return el ? JSON.parse(el.textContent) : null;
    }

    function reais(valor) {
        return 'R$ ' + Number(valor).toLocaleString('pt-BR', {
            minimumFractionDigits: 2, maximumFractionDigits: 2,
        });
    }

    // Se o CDN do Chart.js não carregou (sem internet), avisa em vez de quebrar.
    function avisarSemBiblioteca(canvas) {
        if (!canvas) return;
        const aviso = document.createElement('p');
        aviso.className = 'text-muted';
        aviso.textContent = 'Não foi possível carregar a biblioteca de gráficos.';
        canvas.replaceWith(aviso);
    }

    const canvasSerie = document.getElementById('grafico-serie');
    const canvasEstoque = document.getElementById('grafico-estoque');

    if (typeof Chart === 'undefined') {
        avisarSemBiblioteca(canvasSerie);
        avisarSemBiblioteca(canvasEstoque);
        return;
    }

    // Série: faturamento bruto por dia (ou mês)
    const serie = lerDados('dados-serie');
    if (canvasSerie && serie) {
        new Chart(canvasSerie, {
            type: 'line',
            data: {
                labels: serie.map(function (p) { return p.rotulo; }),
                datasets: [{
                    label: 'Faturamento bruto',
                    data: serie.map(function (p) { return p.receita; }),
                    borderColor: '#0d6efd',
                    backgroundColor: 'rgba(13, 110, 253, 0.15)',
                    fill: true,
                    tension: 0.2,
                }],
            },
            options: {
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function (ctx) { return reais(ctx.parsed.y); },
                            afterLabel: function (ctx) {
                                return serie[ctx.dataIndex].pedidos + ' pedido(s)';
                            },
                        },
                    },
                },
                scales: {
                    y: { beginAtZero: true, ticks: { callback: reais } },
                },
            },
        });
    }

    // Distribuição do estoque dos produtos ativos
    const estoque = lerDados('dados-estoque');
    if (canvasEstoque && estoque) {
        new Chart(canvasEstoque, {
            type: 'doughnut',
            data: {
                labels: ['Esgotados', 'Estoque baixo', 'Estoque ok'],
                datasets: [{
                    data: [estoque.esgotados, estoque.baixos, estoque.ok],
                    backgroundColor: ['#dc3545', '#ffc107', '#198754'],
                }],
            },
            options: {
                maintainAspectRatio: false,
                plugins: { legend: { position: 'bottom' } },
            },
        });
    }
})();
