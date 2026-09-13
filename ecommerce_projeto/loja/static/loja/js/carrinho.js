// carrinho.js
// -----------
// JavaScript bem simples, só para melhorar a experiência do usuário.
// Toda a lógica "de verdade" (cálculo de total, baixa de estoque) fica no
// backend (Django), por segurança: nunca confiamos em cálculos feitos só no
// navegador para decidir quanto o cliente vai pagar.

document.addEventListener('DOMContentLoaded', function () {
    // Fecha automaticamente os alertas de mensagem (sucesso/erro) depois de
    // alguns segundos, para não ficarem poluindo a tela.
    const alertas = document.querySelectorAll('.alert');
    alertas.forEach(function (alerta) {
        setTimeout(function () {
            // Usa o componente de Alert do próprio Bootstrap para fechar com animação.
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alerta);
            bsAlert.close();
        }, 4000);
    });
});
