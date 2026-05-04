// problems.js – CodeMaster Problems Page interactive filtering & progress

document.addEventListener('DOMContentLoaded', function() {
    // DOM elements
    const tbody = document.getElementById('problemsTableBody');
    const rows = Array.from(document.querySelectorAll('#problemsTableBody .problem-row'));
    const searchInput = document.getElementById('searchInput');
    const difficultyBtns = document.querySelectorAll('.filter-btn');
    const statusSelect = document.getElementById('statusFilter');
    const noResultsDiv = document.getElementById('noResultsMsg');
    const paginationInfo = document.getElementById('paginationInfo');
    const paginationList = document.getElementById('paginationList');

    let currentPage = 1;
    const rowsPerPage = 10;
    let filteredRows = [...rows];

    // ---- Helper: update progress stats from visible rows (solved data) ----
    function updateProgressStats() {
        // In real implementation, solved status comes from backend via dataset.
        // For this UI, we simulate using data-solved attribute.
        const easyTotal = rows.filter(r => r.getAttribute('data-difficulty') === 'Easy').length;
        const mediumTotal = rows.filter(r => r.getAttribute('data-difficulty') === 'Medium').length;
        const hardTotal = rows.filter(r => r.getAttribute('data-difficulty') === 'Hard').length;

        const easySolved = rows.filter(r => r.getAttribute('data-difficulty') === 'Easy' && r.getAttribute('data-solved') === 'true').length;
        const mediumSolved = rows.filter(r => r.getAttribute('data-difficulty') === 'Medium' && r.getAttribute('data-solved') === 'true').length;
        const hardSolved = rows.filter(r => r.getAttribute('data-difficulty') === 'Hard' && r.getAttribute('data-solved') === 'true').length;

        document.getElementById('easySolvedCount').innerText = easySolved;
        document.getElementById('easyTotalCount').innerText = easyTotal;
        document.getElementById('mediumSolvedCount').innerText = mediumSolved;
        document.getElementById('mediumTotalCount').innerText = mediumTotal;
        document.getElementById('hardSolvedCount').innerText = hardSolved;
        document.getElementById('hardTotalCount').innerText = hardTotal;

        const easyPercent = easyTotal ? Math.round((easySolved/easyTotal)*100) : 0;
        const mediumPercent = mediumTotal ? Math.round((mediumSolved/mediumTotal)*100) : 0;
        const hardPercent = hardTotal ? Math.round((hardSolved/hardTotal)*100) : 0;
        document.getElementById('easyPercent').innerHTML = easyPercent + '%';
        document.getElementById('mediumPercent').innerHTML = mediumPercent + '%';
        document.getElementById('hardPercent').innerHTML = hardPercent + '%';

        function setCircularProgress(elementId, percent) {
            const ring = document.getElementById(elementId);
            if(ring) {
                const conicDegree = (percent / 100) * 360;
                ring.style.background = `conic-gradient(var(--primary) ${conicDegree}deg, #2A2A4A 0deg)`;
            }
        }
        setCircularProgress('easyProgressCircle .progress-ring', easyPercent);
        setCircularProgress('mediumProgressCircle .progress-ring', mediumPercent);
        setCircularProgress('hardProgressCircle .progress-ring', hardPercent);
    }

    // ---- Filter logic (search + difficulty + status) ----
    function applyFilters() {
        const searchTerm = searchInput ? searchInput.value.toLowerCase() : '';
        const activeDifficulty = document.querySelector('.filter-btn.active')?.getAttribute('data-difficulty') || 'all';
        const statusValue = statusSelect ? statusSelect.value : 'all';

        filteredRows = rows.filter(row => {
            const title = row.getAttribute('data-title') || '';
            const difficulty = row.getAttribute('data-difficulty') || '';
            const solved = row.getAttribute('data-solved') === 'true';

            let matchesSearch = title.includes(searchTerm);
            let matchesDifficulty = (activeDifficulty === 'all') || (difficulty === activeDifficulty);
            let matchesStatus = true;
            if(statusValue === 'solved') matchesStatus = solved;
            if(statusValue === 'unsolved') matchesStatus = !solved;

            return matchesSearch && matchesDifficulty && matchesStatus;
        });

        // No results message
        if(filteredRows.length === 0) {
            noResultsDiv.style.display = 'block';
            tbody.innerHTML = '';
            const emptyMsg = document.createElement('tr');
            emptyMsg.innerHTML = `<td colspan="4" class="text-center py-4">No problems found</td>`;
            tbody.appendChild(emptyMsg);
            paginationInfo.innerText = 'Showing 0 to 0 of 0 problems';
            paginationList.innerHTML = '';
            return;
        } else {
            noResultsDiv.style.display = 'none';
        }

        currentPage = 1;
        renderPage();
        updateProgressStats();
    }

    function renderPage() {
        const start = (currentPage - 1) * rowsPerPage;
        const end = start + rowsPerPage;
        const pageRows = filteredRows.slice(start, end);

        tbody.innerHTML = '';
        pageRows.forEach(row => {
            tbody.appendChild(row.cloneNode(true));
        });
        // re-attach click listeners on cloned rows (already have onclick)
        const total = filteredRows.length;
        const from = start+1;
        const to = Math.min(end, total);
        paginationInfo.innerText = `Showing ${from} to ${to} of ${total} problems`;
        setupPagination(total);
    }

    function setupPagination(totalItems) {
        const totalPages = Math.ceil(totalItems / rowsPerPage);
        paginationList.innerHTML = '';
        if(totalPages <= 1) return;
        // previous
        const prevLi = document.createElement('li');
        prevLi.className = `page-item ${currentPage === 1 ? 'disabled' : ''}`;
        prevLi.innerHTML = `<a class="page-link" href="#">«</a>`;
        prevLi.addEventListener('click', (e) => {
            e.preventDefault();
            if(currentPage > 1) { currentPage--; renderPage(); }
        });
        paginationList.appendChild(prevLi);

        for(let i=1; i<=totalPages; i++) {
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
        nextLi.innerHTML = `<a class="page-link" href="#">»</a>`;
        nextLi.addEventListener('click', (e) => {
            e.preventDefault();
            if(currentPage < totalPages) { currentPage++; renderPage(); }
        });
        paginationList.appendChild(nextLi);
    }

    // ---- Event Listeners ----
    if(searchInput) searchInput.addEventListener('input', applyFilters);
    if(statusSelect) statusSelect.addEventListener('change', applyFilters);
    difficultyBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            difficultyBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            applyFilters();
        });
    });

    // Initialize progress and filter
    updateProgressStats();
    applyFilters();
});