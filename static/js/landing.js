// landing.js – CodeMaster Landing Page Interactions

document.addEventListener('DOMContentLoaded', function() {
    // ---------- Navbar shadow on scroll ----------
    const navbar = document.getElementById('mainNavbar');
    window.addEventListener('scroll', () => {
        if (window.scrollY > 20) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
    });

    // ---------- Floating code particles in hero ----------
    const container = document.getElementById('floatingCodeContainer');
    if (container) {
        const codeSnippets = [
            'def solve():', 'const ans = [];', 'SELECT * FROM users;',
            'class Solution:', 'React.useState()', 'git commit -m "feat"',
            'npm start', 'while True:', 'System.out.println()',
            'docker run', 'for i in range(n):', 'return result'
        ];
        function createFloatingCode() {
            const snippet = document.createElement('div');
            snippet.classList.add('floating-code-snippet');
            snippet.textContent = codeSnippets[Math.floor(Math.random() * codeSnippets.length)];
            const size = 0.8 + Math.random() * 0.6;
            snippet.style.fontSize = `${size}rem`;
            snippet.style.left = `${Math.random() * 100}%`;
            snippet.style.animationDuration = `${8 + Math.random() * 12}s`;
            snippet.style.animationDelay = `${Math.random() * 5}s`;
            snippet.style.opacity = 0.2 + Math.random() * 0.3;
            container.appendChild(snippet);
            setTimeout(() => { if(snippet.parentNode) snippet.remove(); }, 15000);
        }
        setInterval(createFloatingCode, 800);
        for(let i=0; i<15; i++) setTimeout(createFloatingCode, i*200);
    }

    // ---------- Counter Animation (Stats) ----------
    const statsSection = document.getElementById('statsSection');
    let counted = false;
    function animateNumbers() {
        const counters = document.querySelectorAll('.stat-number');
        counters.forEach(counter => {
            const target = parseInt(counter.getAttribute('data-target'));
            if(isNaN(target)) return;
            let current = 0;
            const increment = target / 70;
            const updateCounter = () => {
                current += increment;
                if(current < target) {
                    counter.innerText = Math.floor(current);
                    requestAnimationFrame(updateCounter);
                } else {
                    counter.innerText = target;
                }
            };
            updateCounter();
        });
    }
    function isElementInViewport(el) {
        const rect = el.getBoundingClientRect();
        return rect.top < window.innerHeight - 100 && rect.bottom > 0;
    }
    window.addEventListener('scroll', () => {
        if(!counted && statsSection && isElementInViewport(statsSection)) {
            counted = true;
            animateNumbers();
        }
    });
    if(statsSection && isElementInViewport(statsSection)) {
        counted = true;
        animateNumbers();
    }

    // ---------- Scroll Reveal Animation ----------
    const revealElements = document.querySelectorAll('.reveal-on-scroll');
    function revealOnScroll() {
        revealElements.forEach(el => {
            const rect = el.getBoundingClientRect();
            if(rect.top < window.innerHeight - 80) {
                el.classList.add('revealed');
            }
        });
    }
    window.addEventListener('scroll', revealOnScroll);
    revealOnScroll(); // initial check
});