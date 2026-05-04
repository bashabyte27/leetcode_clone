// auth.js – BashaByte login/register interactions
document.addEventListener('DOMContentLoaded', function() {
    // ---------- Floating Code Animation (left side) ----------
    const container = document.getElementById('floatingCodeBg');
    if (container) {
        const snippets = [
            'def solve():', 'class Solution:', 'SELECT * FROM users;',
            'const result = [];', 'while(n-- > 0)', 'System.out.println()',
            'npm start', 'git commit', 'docker run -p 8000:8000',
            'function dfs(node)', 'dp[i] = dp[i-1] + dp[i-2]', '❯ python manage.py runserver'
        ];
        function createFloating() {
            const el = document.createElement('div');
            el.classList.add('floating-code');
            el.innerText = snippets[Math.floor(Math.random() * snippets.length)];
            const size = 0.7 + Math.random() * 0.5;
            el.style.fontSize = `${size}rem`;
            el.style.left = `${Math.random() * 100}%`;
            el.style.animationDuration = `${10 + Math.random() * 15}s`;
            el.style.animationDelay = `${Math.random() * 5}s`;
            container.appendChild(el);
            setTimeout(() => { if(el.parentNode) el.remove(); }, 15000);
        }
        setInterval(createFloating, 700);
        for(let i=0;i<12;i++) setTimeout(createFloating, i*300);
    }

    // ---------- Password Toggle (show/hide) ----------
    const toggles = document.querySelectorAll('.toggle-password');
    toggles.forEach(toggle => {
        toggle.addEventListener('click', function(e) {
            const targetId = this.getAttribute('toggle-target');
            const input = document.querySelector(targetId);
            if (input) {
                const type = input.getAttribute('type') === 'password' ? 'text' : 'password';
                input.setAttribute('type', type);
                this.querySelector('i').classList.toggle('fa-eye-slash');
                this.querySelector('i').classList.toggle('fa-eye');
            }
        });
    });

    // ---------- Password Strength Meter (register page only) ----------
    const regPassword = document.getElementById('regPassword');
    const strengthBar = document.getElementById('strengthBar');
    const strengthText = document.getElementById('strengthText');
    if (regPassword) {
        regPassword.addEventListener('input', function() {
            const val = this.value;
            let strength = 0;
            if (val.length >= 6) strength++;
            if (val.length >= 10) strength++;
            if (/[A-Z]/.test(val)) strength++;
            if (/[0-9]/.test(val)) strength++;
            if (/[^A-Za-z0-9]/.test(val)) strength++;
            let score = Math.min(5, strength);
            let percent = (score / 5) * 100;
            strengthBar.style.width = percent + '%';
            let color = '#E5484D', text = 'Weak';
            if (score >= 3 && score < 4) { color = '#F76808'; text = 'Medium'; }
            else if (score >= 4) { color = '#30A46C'; text = 'Strong'; }
            strengthBar.style.background = color;
            strengthText.innerText = text + ' password';
            if (val.length === 0) strengthText.innerText = 'Enter a strong password';
        });
    }

    // ---------- Confirm Password Match Checker ----------
    const confirmPw = document.getElementById('confirmPassword');
    const matchIcon = document.getElementById('passwordMatchIcon');
    if (confirmPw && regPassword) {
        function checkMatch() {
            if (confirmPw.value === regPassword.value && regPassword.value.length > 0) {
                matchIcon.innerHTML = '<i class="fas fa-check-circle" style="color:#30A46C;"></i>';
                matchIcon.style.display = 'inline-block';
            } else if (confirmPw.value.length > 0) {
                matchIcon.innerHTML = '<i class="fas fa-times-circle" style="color:#E5484D;"></i>';
                matchIcon.style.display = 'inline-block';
            } else {
                matchIcon.style.display = 'none';
            }
        }
        regPassword.addEventListener('input', checkMatch);
        confirmPw.addEventListener('input', checkMatch);
    }

    // ---------- Form Validation before submit (client-side hints) ----------
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', function(e) {
            const username = loginForm.querySelector('input[name="username"]');
            const password = loginForm.querySelector('input[name="password"]');
            if (!username.value.trim() || !password.value.trim()) {
                e.preventDefault();
                showTemporaryError(loginForm, 'Both fields are required.');
            }
        });
    }
    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        registerForm.addEventListener('submit', function(e) {
            const fullName = registerForm.querySelector('input[name="full_name"]');
            const username = registerForm.querySelector('input[name="username"]');
            const email = registerForm.querySelector('input[name="email"]');
            const pwd = registerForm.querySelector('input[name="password"]');
            const confirm = registerForm.querySelector('input[name="confirm_password"]');
            const terms = document.getElementById('termsCheck');
            if (!fullName.value.trim() || !username.value.trim() || !email.value.trim() || !pwd.value.trim() || !confirm.value.trim()) {
                e.preventDefault();
                showTemporaryError(registerForm, 'All fields are required.');
                return;
            }
            if (pwd.value !== confirm.value) {
                e.preventDefault();
                showTemporaryError(registerForm, 'Passwords do not match.');
                return;
            }
            if (!terms.checked) {
                e.preventDefault();
                showTemporaryError(registerForm, 'You must agree to the Terms.');
            }
        });
    }
    function showTemporaryError(form, msg) {
        let errorDiv = form.querySelector('.form-error-global');
        if (!errorDiv) {
            errorDiv = document.createElement('div');
            errorDiv.className = 'alert alert-danger shake-error mt-3';
            errorDiv.style.fontSize = '0.85rem';
            form.prepend(errorDiv);
        }
        errorDiv.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${msg}`;
        setTimeout(() => { if(errorDiv) errorDiv.remove(); }, 3000);
    }
});