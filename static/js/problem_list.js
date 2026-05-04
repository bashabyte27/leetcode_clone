// problem_list.js – BashaByte interactive filtering & animations

document.addEventListener('DOMContentLoaded', function() {
    // DOM elements
    const tbody = document.getElementById('problemsTbody');
    const originalRows = Array.from(document.querySelectorAll('#problemsTbody .problem-row'));
    const searchInput = document.getElementById('problemSearch');
    const difficultyBtns = document.querySelectorAll('.filter-pill');
    const statusSelect = document.getElementById('statusFilter');
    const noResultsDiv = document.getElementById('noResultsMsg');
    const paginationInfo = document.getElementById('paginationInfo');
    const paginationList = document.getElementById('paginationList');

    let currentPage = 1;
    const rowsPerPage = 10;
    let filteredRows = [...originalRows];

    // ---------- ACCEPTANCE BAR ANIMATION ----------
    function animateAcceptanceBars() {
        const fills = document.querySelectorAll('.acceptance-fill');
        fills.forEach(fill => {
            const width = fill.getAttribute('data-width') || 0;
            fill.style.width = width + '%';
        });
    }
    animateAcceptanceBars();

    // ---------- UPDATE PROGRESS CIRCLE (if user logged in) ----------
    function updateProgressCircle() {
        const solvedStats = document.querySelectorAll('.progress-stats span');
        if (!solvedStats.length) return;
        // Simulate solved counts from localStorage or from backend attribute.
        // For demo, we calculate based on rows with data-status="solved"
        const solvedRows = originalRows.filter(row => row.getAttribute('data-status') === 'solved');
        let easyTotal = window.problemCounts?.easyTotal || 0;
        let mediumTotal = window.problemCounts?.mediumTotal || 0;
        let hardTotal = window.problemCounts?.hardTotal || 0;
        
        let easySolved = 0, mediumSolved = 0, hardSolved = 0;
        solvedRows.forEach(row => {
            const diff = row.getAttribute('data-difficulty');
            if (diff === 'Easy') easySolved++;
            else if (diff === 'Medium') mediumSolved++;
            else if (diff === 'Hard') hardSolved++;
        });
        document.getElementById('easySolvedStats') && (document.getElementById('easySolvedStats').innerText = easySolved);
        document.getElementById('mediumSolvedStats') && (document.getElementById('mediumSolvedStats').innerText = mediumSolved);
        document.getElementById('hardSolvedStats') && (document.getElementById('hardSolvedStats').innerText = hardSolved);
        
        const totalSolved = easySolved + mediumSolved + hardSolved;
        const totalProblems = easyTotal + mediumTotal + hardTotal;
        const percent = totalProblems ? (totalSolved / totalProblems) * 100 : 0;
        const percentElement = document.getElementById('progressPercent');
        if (percentElement) percentElement.innerText = Math.round(percent) + '%';
        const ring = document.querySelector('.progress-ring');
        if (ring) {
            const deg = (percent / 100) * 360;
            ring.style.background = `conic-gradient(var(--primary) ${deg}deg, #2A2A4A 0deg)`;
        }
    }
    updateProgressCircle();

    // ---------- FILTER LOGIC (search + difficulty + status) ----------
    function applyFilters() {
        const searchTerm = searchInput ? searchInput.value.trim().toLowerCase() : '';
        const activeDifficulty = document.querySelector('.filter-pill.active')?.getAttribute('data-difficulty') || 'all';
        const statusValue = statusSelect ? statusSelect.value : 'all';

        filteredRows = originalRows.filter(row => {
            const title = row.getAttribute('data-title') || '';
            const difficulty = row.getAttribute('data-difficulty') || '';
            const status = row.getAttribute('data-status') || 'unsolved';

            const matchesSearch = title.includes(searchTerm);
            const matchesDifficulty = (activeDifficulty === 'all') || (difficulty === activeDifficulty);
            const matchesStatus = (statusValue === 'all') || (statusValue === status);
            return matchesSearch && matchesDifficulty && matchesStatus;
        });

        if (filteredRows.length === 0) {
            noResultsDiv.style.display = 'block';
            tbody.innerHTML = '';
            const emptyRow = document.createElement('tr');
            emptyRow.innerHTML = `<td colspan="5" class="text-center py-5"><i class="fas fa-frown-open"></i> No problems found :(</td>`;
            tbody.appendChild(emptyRow);
            paginationInfo.innerText = 'Showing 0 to 0 of 0 problems';
            paginationList.innerHTML = '';
            return;
        }
        noResultsDiv.style.display = 'none';
        currentPage = 1;
        renderPage();
    }

    function renderPage() {
        const start = (currentPage - 1) * rowsPerPage;
        const end = start + rowsPerPage;
        const pageRows = filteredRows.slice(start, end);
        tbody.innerHTML = '';
        pageRows.forEach(row => {
            tbody.appendChild(row.cloneNode(true));
        });
        // reattach click listeners (already have onclick attribute)
        const total = filteredRows.length;
        const from = start + 1;
        const to = Math.min(end, total);
        paginationInfo.innerText = `Showing ${from} to ${to} of ${total} problems`;
        setupPagination(total);
        // re-animate acceptance bars for new visible rows
        document.querySelectorAll('.acceptance-fill').forEach(fill => {
            const width = fill.getAttribute('data-width') || 0;
            fill.style.width = width + '%';
        });
    }

    function setupPagination(totalItems) {
        const totalPages = Math.ceil(totalItems / rowsPerPage);
        paginationList.innerHTML = '';
        if (totalPages <= 1) return;
        // Previous button
        const prevLi = document.createElement('li');
        prevLi.className = `page-item ${currentPage === 1 ? 'disabled' : ''}`;
        prevLi.innerHTML = `<a class="page-link" href="#"><i class="fas fa-chevron-left"></i></a>`;
        prevLi.addEventListener('click', (e) => {
            e.preventDefault();
            if (currentPage > 1) { currentPage--; renderPage(); }
        });
        paginationList.appendChild(prevLi);

        for (let i = 1; i <= totalPages; i++) {
            const li = document.createElement('li');
            li.className = `page-item ${i === currentPage ? 'active' : ''}`;
            li.innerHTML = `<a class="page-link" href="#">${i}</a>`;
            li.addEventListener('click', (e) => {
                e.preventDefault();
                currentPage = i;
                renderPage();
            });
            paginationList.appendChild(li);
        }

        const nextLi = document.createElement('li');
        nextLi.className = `page-item ${currentPage === totalPages ? 'disabled' : ''}`;
        nextLi.innerHTML = `<a class="page-link" href="#"><i class="fas fa-chevron-right"></i></a>`;
        nextLi.addEventListener('click', (e) => {
            e.preventDefault();
            if (currentPage < totalPages) { currentPage++; renderPage(); }
        });
        paginationList.appendChild(nextLi);
    }

    // ---------- EVENT LISTENERS ----------
    if (searchInput) searchInput.addEventListener('input', applyFilters);
    if (statusSelect) statusSelect.addEventListener('change', applyFilters);
    difficultyBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            difficultyBtns.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            applyFilters();
        });
    });

    // ---------- TOP TAGS FILTERING (simulate search) ----------
    const tags = document.querySelectorAll('.topic-tag');
    tags.forEach(tag => {
        tag.addEventListener('click', function() {
            const tagText = this.innerText.toLowerCase();
            if (searchInput) {
                searchInput.value = tagText;
                applyFilters();
            }
        });
    });

    // initial render
    applyFilters();

    // Sticky filter bar effect (already sticky via CSS, but add shadow)
    const filterBar = document.getElementById('filterBar');
    window.addEventListener('scroll', () => {
        if (window.scrollY > 100) {
            filterBar.style.boxShadow = '0 4px 20px rgba(0,0,0,0.3)';
        } else {
            filterBar.style.boxShadow = 'none';
        }
    });
});