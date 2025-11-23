// --- CONFIGURATION ---
const API_BASE_URL = "http://localhost:8000";

// --- STATE MANAGEMENT ---
const defaultTaxonomy = ['Food & Dining', 'Transportation', 'Utilities', 'Housing', 'Shopping', 'Entertainment', 'Health & Fitness', 'Income', 'Transfer', 'Uncategorized'];

// Load from localStorage (may be overwritten by server on init)
let taxonomy = JSON.parse(localStorage.getItem('taxonomy')) || defaultTaxonomy;
let transactions = JSON.parse(localStorage.getItem('transactions')) || [];

// --- DOM ELEMENTS ---
const dom = {
    data: document.getElementById('input-data'),
    results: document.getElementById('results-container'),
    empty: document.getElementById('empty-state'),
    queueCount: document.getElementById('queue-count'),
    actionBar: document.getElementById('action-bar'),
    reviewedCount: document.getElementById('reviewed-count'),
    taxonomyList: document.getElementById('taxonomy-list'),
    newCatInput: document.getElementById('new-category'),
    // Dashboard
    dashTotal: document.getElementById('dash-total'),
    dashAutoRate: document.getElementById('dash-auto-rate'),
    dashPending: document.getElementById('dash-pending'),
    dashAccuracy: document.getElementById('dash-accuracy'),
    dashDist: document.getElementById('dash-distribution-container')
};

// --- INITIALIZATION ---
init();

async function init() {
    await loadTaxonomyFromServer();   // <--- NEW

    renderTaxonomy();
    renderDashboard();
    
    // Restore view if we have data, otherwise show empty queue
    if (transactions.length > 0) {
        renderResults();
    }
}

// NEW: fetch taxonomy from /categories and sync to local state
async function loadTaxonomyFromServer() {
    try {
        const res = await fetch(`${API_BASE_URL}/categories`);
        if (!res.ok) throw new Error('Failed to load categories from API');

        const data = await res.json();
        if (Array.isArray(data.categories) && data.categories.length > 0) {
            taxonomy = data.categories;
            localStorage.setItem('taxonomy', JSON.stringify(taxonomy));
        }
    } catch (err) {
        console.warn('Using local taxonomy fallback:', err.message);
        // keep existing taxonomy (localStorage or defaultTaxonomy)
    }
}

// --- NAVIGATION ---
function switchTab(tabName) {
    ['dashboard', 'classify', 'taxonomy'].forEach(t => {
        document.getElementById(`view-${t}`).classList.add('hidden');
        const btn = document.getElementById(`nav-${t}`);
        btn.classList.remove('bg-white', 'shadow-sm', 'text-primary');
        btn.classList.add('text-slate-500');
    });

    document.getElementById(`view-${tabName}`).classList.remove('hidden');
    const activeBtn = document.getElementById(`nav-${tabName}`);
    activeBtn.classList.add('bg-white', 'shadow-sm', 'text-primary');
    activeBtn.classList.remove('text-slate-500');

    if(tabName === 'taxonomy') renderTaxonomy();
    if(tabName === 'dashboard') renderDashboard();
}

// --- CORE LOGIC: PROCESS DATA ---
async function processData() {
    const rawText = dom.data.value.trim();
    if (!rawText) return showToast('Please enter some data first.');

    const btn = document.getElementById('btn-analyze');
    const originalBtnHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> Sending to API...`;

    try {
        // 1. Local Parsing
        const newBatch = rawText.split('\n').map((line, index) => {
            if(!line.trim()) return null;
            const parts = line.split(',');
            // Heuristic CSV parsing
            const date = (parts[0] && parts[0].includes('-')) ? parts[0].trim() : new Date().toISOString().split('T')[0];
            const description = parts[1] ? parts[1].trim() : (parts[0] || 'Unknown');
            const amount = parts[2] ? parts[2].trim() : '0.00';
            return { id: Date.now() + index, date, description, amount };
        }).filter(x => x);

        if(newBatch.length === 0) throw new Error("No valid lines found");

        // 2. Call Batch API
        const descriptions = newBatch.map(t => t.description);
        
        const response = await fetch(`${API_BASE_URL}/categorize/batch`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ transactions: descriptions })
        });

        if (!response.ok) throw new Error('API Request Failed: ' + response.statusText);

        const data = await response.json();
        // Handle API returning object with 'predictions' key or direct array
        const predictions = Array.isArray(data) ? data : (data.predictions || data.categories || []);

        // 3. Merge Results
        const processedTransactions = newBatch.map((tx, i) => {
            const pred = predictions[i];
            let category = 'Uncategorized';
            let confidence = 0.5; // Default median confidence if missing
            let explanation = 'Classified via API';

            // Handle various API response formats (string or object)
            if (typeof pred === 'string') {
                category = pred;
                confidence = 0.9; 
            } else if (typeof pred === 'object' && pred !== null) {
                category = pred.category || category;
                confidence = pred.confidence !== undefined ? pred.confidence : confidence;
                explanation = pred.explanation || explanation;
            }

            return {
                ...tx,
                predictedCategory: category,
                currentCategory: category,
                confidence: confidence,
                explanation: explanation,
                isCorrected: false,
                status: 'pending' // pending review
            };
        });

        // 4. Update State
        transactions = [...transactions, ...processedTransactions];
        saveData();
        renderResults();
        showToast(`${processedTransactions.length} transactions categorized`);
        dom.data.value = ''; 

    } catch (error) {
        console.error(error);
        showToast('Error: ' + error.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalBtnHtml;
    }
}

// --- CORE LOGIC: FEEDBACK ---
async function submitFeedback() {
    const corrections = transactions.filter(t => t.isCorrected && t.status !== 'submitted');
    
    if (corrections.length === 0) {
        // If no corrections, just mark all pending as done
        transactions.forEach(t => t.status = 'submitted');
        saveData();
        renderResults();
        return showToast("Review marked as complete.");
    }

    dom.actionBar.innerHTML = `<div class="w-full text-center text-primary font-bold"><i class="fa-solid fa-circle-notch fa-spin"></i> Sending ${corrections.length} corrections...</div>`;

    try {
        // Send corrections sequentially or in parallel
        // The curl example implies single item POST: /correct
        const promises = corrections.map(tx => 
            fetch(`${API_BASE_URL}/correct`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    transaction: tx.description,
                    correct_category: tx.currentCategory
                })
            })
        );

        await Promise.all(promises);

        // Mark all as submitted
        transactions.forEach(t => t.status = 'submitted');
        saveData();
        
        showToast('Model updated with feedback!');
        renderResults();

    } catch (error) {
        console.error(error);
        showToast("Failed to submit corrections: " + error.message);
    } finally {
         // Reset Action Bar
         dom.actionBar.innerHTML = `
             <div class="text-sm text-slate-500">
                <span id="reviewed-count">0</span> transactions corrected
            </div>
            <button onclick="submitFeedback()" class="bg-slate-800 hover:bg-black text-white px-6 py-2 rounded-lg text-sm font-medium transition-all shadow-md">
                Confirm & Train Model
            </button>
        `;
    }
}

// --- DASHBOARD RENDERING ---
function renderDashboard() {
    if (transactions.length === 0) return;

    // Calculate Stats
    const total = transactions.length;
    const pending = transactions.filter(t => t.status !== 'submitted').length;
    const highConf = transactions.filter(t => t.confidence >= 0.8).length;
    const corrections = transactions.filter(t => t.isCorrected).length;
    
    // Derived metrics
    const accuracy = total > 0 ? Math.round(((total - corrections) / total) * 100) : 100;
    const autoRate = total > 0 ? Math.round((highConf / total) * 100) : 0;

    dom.dashTotal.innerText = total;
    dom.dashPending.innerText = pending;
    dom.dashAccuracy.innerText = `${accuracy}%`;
    dom.dashAutoRate.innerText = `${autoRate}%`;

    // Distribution Graph
    const counts = {};
    transactions.forEach(t => {
        counts[t.currentCategory] = (counts[t.currentCategory] || 0) + 1;
    });

    // Sort by count descending
    const sortedCats = Object.keys(counts).sort((a,b) => counts[b] - counts[a]).slice(0, 5); // Top 5

    dom.dashDist.innerHTML = sortedCats.map(cat => {
        const pct = Math.round((counts[cat] / total) * 100);
        return `
            <div>
                <div class="flex justify-between text-sm mb-1">
                    <span class="font-medium text-slate-700">${cat}</span>
                    <span class="font-medium text-slate-500">${pct}%</span>
                </div>
                <div class="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden">
                    <div class="bg-primary h-2.5 rounded-full transition-all duration-1000 ease-out" style="width: ${pct}%"></div>
                </div>
            </div>
        `;
    }).join('');
}

// --- UI RENDERERS ---
function renderResults(filter = 'all') {
    const queue = transactions.filter(t => t.status !== 'submitted');

    dom.results.innerHTML = '';
    dom.queueCount.innerText = queue.length;
    
    if (queue.length === 0) {
        dom.empty.classList.remove('hidden');
        dom.actionBar.classList.remove('translate-y-0');
        dom.actionBar.classList.add('translate-y-full');
        return;
    }

    dom.empty.classList.add('hidden');
    dom.actionBar.classList.remove('translate-y-full');
    dom.actionBar.classList.add('translate-y-0');

    queue.forEach((tx, index) => {
        if (filter === 'low' && tx.confidence > 0.6) return;

        let confBg = tx.confidence < 0.6 ? 'bg-red-100 text-red-700 border-red-200' : 
                     tx.confidence < 0.8 ? 'bg-yellow-100 text-yellow-800 border-yellow-200' : 
                     'bg-green-100 text-green-700 border-green-200';

        const card = document.createElement('div');
        card.className = 'bg-white rounded-xl p-4 shadow-sm border border-slate-200 animate-fade-in hover:shadow-md transition-shadow';
        
        card.innerHTML = `
            <div class="flex flex-col md:flex-row gap-4 items-start md:items-center justify-between">
                <div class="flex-1">
                    <div class="flex items-center gap-3 mb-1">
                        <div class="text-xs font-mono text-slate-400 bg-slate-100 px-2 py-0.5 rounded">${tx.date}</div>
                        <div class="text-xs font-bold px-2 py-0.5 rounded border ${confBg} flex items-center gap-1">
                            <i class="fa-solid fa-robot"></i> ${Math.floor(tx.confidence * 100)}%
                        </div>
                    </div>
                    <div class="font-semibold text-slate-800 text-lg">${tx.description}</div>
                    <div class="text-sm text-slate-500 mt-1"><i class="fa-solid fa-wand-magic-sparkles text-primary text-xs"></i> ${tx.explanation}</div>
                </div>
                <div class="text-right min-w-[100px]">
                    <div class="font-mono font-medium ${tx.amount.includes('-') ? 'text-slate-800' : 'text-green-600'}">${tx.amount}</div>
                </div>
                <div class="w-full md:w-64">
                    <label class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1 block">Category</label>
                    <div class="relative">
                        <select onchange="updateTransaction(${tx.id}, this.value)" 
                            class="w-full appearance-none bg-slate-50 border ${tx.isCorrected ? 'border-primary bg-indigo-50' : 'border-slate-200'} text-slate-700 py-2 px-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary font-medium">
                            ${taxonomy.map(cat => `<option value="${cat}" ${cat === tx.currentCategory ? 'selected' : ''}>${cat}</option>`).join('')}
                        </select>
                        <div class="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-slate-500"><i class="fa-solid fa-chevron-down text-xs"></i></div>
                    </div>
                    ${tx.isCorrected ? `<div class="text-xs text-primary mt-1 font-medium"><i class="fa-solid fa-pen"></i> Corrected</div>` : ''}
                </div>
            </div>
        `;
        dom.results.appendChild(card);
    });
}

// --- HELPER FUNCTIONS ---
function updateTransaction(id, newCat) {
    const tx = transactions.find(t => t.id === id);
    if (tx) {
        tx.currentCategory = newCat;
        tx.isCorrected = tx.currentCategory !== tx.predictedCategory;
        saveData();
        renderResults(); 
        updateCorrectionCount();
    }
}

function updateCorrectionCount() {
    const count = transactions.filter(t => t.isCorrected && t.status !== 'submitted').length;
    dom.reviewedCount.innerText = count;
}

function filterQueue(type) {
    renderResults(type);
}

function saveData() {
    localStorage.setItem('transactions', JSON.stringify(transactions));
    localStorage.setItem('taxonomy', JSON.stringify(taxonomy));
    renderDashboard(); // Update dashboard whenever data changes
}

function clearHistory() {
    if(confirm("Clear all local history and stats?")) {
        transactions = [];
        saveData();
        renderDashboard();
        renderResults();
        showToast("History cleared.");
    }
}

// --- TAXONOMY ---
function renderTaxonomy() {
    dom.taxonomyList.innerHTML = taxonomy.map(cat => `
        <div class="flex items-center justify-between p-3 bg-white border border-slate-200 rounded-lg group">
            <span class="font-medium text-slate-700">${cat}</span>
            <button onclick="removeCategory('${cat}')" class="text-slate-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"><i class="fa-solid fa-trash"></i></button>
        </div>
    `).join('');
}

function addCategory() {
    const val = dom.newCatInput.value.trim();
    if (val && !taxonomy.includes(val)) {
        taxonomy.push(val);
        dom.newCatInput.value = '';
        saveData();
        renderTaxonomy();
        showToast(`Category "${val}" added`);
    }
}

function removeCategory(cat) {
    if (confirm(`Delete "${cat}"?`)) {
        taxonomy = taxonomy.filter(c => c !== cat);
        saveData();
        renderTaxonomy();
    }
}

function resetTaxonomy() {
    if(confirm("Reset categories?")) {
        taxonomy = [...defaultTaxonomy];
        saveData();
        renderTaxonomy();
    }
}

function showToast(msg) {
    const toast = document.getElementById('toast');
    document.getElementById('toast-message').innerText = msg;
    toast.classList.remove('translate-y-24');
    setTimeout(() => toast.classList.add('translate-y-24'), 3000);
}

// --- DEMO PREFILL ---
if(!dom.data.value) {
    dom.data.value = `2023-11-01, UBER *TRIP 8X92, -24.50\n2023-11-01, WHOLEFDS MRK, -104.22\n2023-11-02, NETFLIX.COM, -20.00`;
}
