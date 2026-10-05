/* 🎃 Tema Halloween — Body-Fit
 *
 *  - Se activa solo hasta el 2 de noviembre (después desaparece sin tocar nada).
 *  - El botón 🎃 del navbar lo activa/desactiva y recuerda la elección.
 *  - Para quitarlo definitivamente: borra las 2 líneas que lo cargan en
 *    base.html / login.html / welcome.html y el botón #hwToggle del navbar.
 */
(function () {
    'use strict';

    // Fin de temporada: 3-nov-2026 00:00 hora Colombia (UTC-5)
    var END = new Date('2026-11-03T05:00:00Z');
    if (new Date() >= END) { return; }

    var KEY  = 'bf-halloween';
    var root = document.documentElement;

    function isOn() {
        try { return localStorage.getItem(KEY) !== 'off'; } catch (e) { return true; }
    }
    function savePref(on) {
        try { localStorage.setItem(KEY, on ? 'on' : 'off'); } catch (e) {}
    }

    // Se aplica en <head> para evitar el "parpadeo" del tema al cargar
    if (isOn()) { root.classList.add('hw'); }

    /* ── SVGs ───────────────────────────────────────────────────── */
    var BAT = '<svg viewBox="0 0 64 40" width="%W%" xmlns="http://www.w3.org/2000/svg">' +
        '<path d="M32 10 L29 3 L28 12 C24 15 20 14 17 11 C11 8 5 11 1 19 C7 17 11 20 13 27 ' +
        'C17 23 22 24 26 31 L29 26 L32 33 L35 26 L38 31 C42 24 47 23 51 27 C53 20 57 17 63 19 ' +
        'C59 11 53 8 47 11 C44 14 40 15 36 12 L35 3 Z"/></svg>';

    var SPIDER = '<svg viewBox="0 0 40 36" xmlns="http://www.w3.org/2000/svg">' +
        '<ellipse cx="20" cy="22" rx="8" ry="9"/><circle cx="20" cy="11" r="5"/>' +
        '<g stroke="#120818" stroke-width="2" fill="none" stroke-linecap="round">' +
        '<path d="M13 18 L3 11 L1 19"/><path d="M13 22 L2 24 L3 33"/>' +
        '<path d="M14 26 L6 33 L9 36"/><path d="M13 14 L6 5 L2 8"/>' +
        '<path d="M27 18 L37 11 L39 19"/><path d="M27 22 L38 24 L37 33"/>' +
        '<path d="M26 26 L34 33 L31 36"/><path d="M27 14 L34 5 L38 8"/></g>' +
        '<circle cx="18" cy="10" r="1.3" fill="#ff3b3b"/><circle cx="22" cy="10" r="1.3" fill="#ff3b3b"/></svg>';

    var GHOST = '<svg viewBox="0 0 48 60" xmlns="http://www.w3.org/2000/svg">' +
        '<path fill="#fff" d="M24 2C11 2 3 12 3 26v30l7-6 7 6 7-6 7 6 7-6 7 6V26C45 12 37 2 24 2z"/>' +
        '<ellipse cx="17" cy="24" rx="3.6" ry="5" fill="#1b0b2e"/>' +
        '<ellipse cx="31" cy="24" rx="3.6" ry="5" fill="#1b0b2e"/>' +
        '<ellipse cx="24" cy="36" rx="4" ry="5.5" fill="#1b0b2e"/></svg>';

    var WEB = '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">' +
        '<g stroke="#fff" fill="none" stroke-width="1.1" stroke-linecap="round">' +
        '<path d="M0 0 L100 0 M0 0 L96 34 M0 0 L82 68 M0 0 L58 90 M0 0 L28 99 M0 0 L0 100"/>' +
        '<path d="M26 0 Q20 20 0 26 M50 0 Q38 38 0 50 M74 0 Q55 55 0 74 M98 0 Q72 72 0 98"/></g></svg>';

    /* ── Construcción / limpieza ────────────────────────────────── */
    function el(html) {
        var d = document.createElement('div');
        d.innerHTML = html;
        return d.firstChild;
    }

    function build() {
        if (document.getElementById('hw-decor')) { return; }
        var standalone = !document.querySelector('.sidebar');   // login / bienvenida

        /* Capa fija: murciélagos, fantasma, luna, niebla */
        var decor = el('<div id="hw-decor" aria-hidden="true"></div>');

        var bats = [  // top, duración, retraso (negativo = ya en vuelo), ancho
            ['9vh',  '19s',  '-3s', 40],
            ['22vh', '26s', '-14s', 30],
            ['38vh', '22s',  '-8s', 34],
            ['58vh', '30s', '-21s', 26],
            ['74vh', '24s',  '-1s', 32]
        ];
        bats.forEach(function (b) {
            var bat = el('<div class="hw-bat"><div class="hw-bat-in">' +
                         BAT.replace('%W%', b[3]) + '</div></div>');
            bat.style.top = b[0];
            bat.style.animationDuration = b[1];
            bat.style.animationDelay = b[2];
            bat.firstChild.style.animationDuration = (3 + b[3] / 10) + 's';
            decor.appendChild(bat);
        });

        decor.appendChild(el('<div class="hw-ghost">' + GHOST + '</div>'));
        if (standalone) {
            decor.appendChild(el('<div class="hw-moon"></div>'));
            decor.appendChild(el('<div class="hw-fog"></div>'));
        }
        document.body.appendChild(decor);

        /* Capa que scrollea con la página: arañas y telarañas del navbar */
        var top = el('<div id="hw-top" aria-hidden="true"></div>');
        top.appendChild(el('<div class="hw-web l">' + WEB + '</div>'));
        top.appendChild(el('<div class="hw-web r">' + WEB + '</div>'));
        // En el sistema quedan "colgadas" dentro del navbar (sin tapar contenido);
        // en login/bienvenida cuelgan más largo.
        var spiders = standalone
            ? [['38%', '78px', '5.2s', ''], ['64%', '100px', '6.4s', ' hide-sm']]
            : [['34%', '16px', '4.6s', ''], ['47%', '26px', '5.4s', ' hide-sm'],
               ['58%', '12px', '6.2s', ' hide-sm']];
        spiders.forEach(function (s) {
            var sp = el('<div class="hw-spider' + s[3] + '"><span class="hw-thread"></span>' + SPIDER + '</div>');
            sp.style.left = s[0];
            sp.style.setProperty('--len', s[1]);
            sp.style.setProperty('--dur', s[2]);
            top.appendChild(sp);
        });
        document.body.insertBefore(top, document.body.firstChild);
    }

    function destroy() {
        ['hw-decor', 'hw-top'].forEach(function (id) {
            var n = document.getElementById(id);
            if (n) { n.remove(); }
        });
    }

    function apply(on) {
        root.classList.toggle('hw', on);
        if (on) { build(); } else { destroy(); }
    }

    document.addEventListener('DOMContentLoaded', function () {
        var btn = document.getElementById('hwToggle');
        if (btn) {
            btn.classList.remove('d-none');          // el botón solo existe en temporada
            btn.addEventListener('click', function () {
                var on = !root.classList.contains('hw');
                savePref(on);
                apply(on);
            });
        }
        apply(isOn());
    });
})();
