/* loading_screen.js */
document.addEventListener('DOMContentLoaded', function() {
    const loadingOverlay = document.getElementById('loading-overlay');
    if (!loadingOverlay) {
        console.error("Loading overlay element not found!");
        return;
    }

    // Function to show the loading screen
    function showLoadingScreen() {
        if (loadingOverlay) {
            loadingOverlay.style.display = 'flex';
            loadingOverlay.classList.remove('hidden');
        }
    }

    // Function to hide the loading screen
    function hideLoadingScreen() {
        if (loadingOverlay) {
            loadingOverlay.classList.add('hidden');
            // Wait for the transition to end before setting display to 'none'
            loadingOverlay.addEventListener('transitionend', function handler() {
                loadingOverlay.style.display = 'none';
                loadingOverlay.removeEventListener('transitionend', handler);
            });
        }
    }

    // Hide the loading screen once the initial page content is loaded
    // We use window.onload to ensure all resources (images, etc.) are loaded
    window.onload = function() {
        hideLoadingScreen();
    };

    // Show loading screen when navigating away from the page
    window.addEventListener('beforeunload', function() {
        showLoadingScreen();
    });

    // Fallback to hide the loading screen if beforeunload is not supported or page is cached
    // The pageshow event is fired when the browser displays the page
    window.addEventListener('pageshow', function(event) {
        // If the page is loaded from the cache, the loading screen might still be visible
        if (event.persisted) {
            hideLoadingScreen();
        }
    });
});

/* transactions.js */
document.addEventListener('DOMContentLoaded', function() {
    const modal = document.getElementById('addTransactionModal');
    const transactionForm = document.getElementById('transactionForm');
    const incomeBtn = document.getElementById('incomeBtn');
    const expenseBtn = document.getElementById('expenseBtn');
    const modalType = document.getElementById('modalType');

    // Function to reset transaction type buttons to unselected state
    function resetTransactionTypeButtons() {
        modalType.value = '';
        incomeBtn.classList.remove('bg-green-600');
        incomeBtn.classList.add('bg-gray-700');
        expenseBtn.classList.remove('bg-red-600');
        expenseBtn.classList.add('bg-gray-700');
    }

    // Function to set the transaction type
    function setTransactionType(type) {
        modalType.value = type;
        if (type === 'income') {
            incomeBtn.classList.remove('bg-gray-700');
            incomeBtn.classList.add('bg-green-600');
            expenseBtn.classList.remove('bg-red-600');
            expenseBtn.classList.add('bg-gray-700');
        } else {
            incomeBtn.classList.remove('bg-green-600');
            incomeBtn.classList.add('bg-gray-700');
            expenseBtn.classList.remove('bg-gray-700');
            expenseBtn.classList.add('bg-red-600');
        }
    }

    // Add event listeners for transaction type buttons
    if (incomeBtn) {
        incomeBtn.addEventListener('click', () => setTransactionType('income'));
    }
    if (expenseBtn) {
        expenseBtn.addEventListener('click', () => setTransactionType('expense'));
    }

    // Function to toggle the modal
    window.toggleAddTransactionModal = function(transaction = null) {
        const modalTitle = document.getElementById('modalTitle');
        const modalIcon = document.getElementById('modalIcon');
        const modalSubmitIcon = document.getElementById('modalSubmitIcon');
        const modalSubmitText = document.getElementById('modalSubmitText');

        if (modal.classList.contains('hidden')) {
            // Adding new transaction
            modalTitle.textContent = 'Add New Transaction';
            modalIcon.className = 'fas fa-plus-circle text-green-400 text-2xl mr-3';
            transactionForm.action = '/add_transaction';
            transactionForm.reset();
            document.getElementById('modalTxId').value = '';
            // Reset transaction type buttons to unselected state
            resetTransactionTypeButtons();
            document.getElementById('modalTransactionDate').value = new Date().toISOString().slice(0, 10);
            modalSubmitIcon.className = 'fas fa-plus mr-2';
            modalSubmitText.textContent = 'Add Transaction';
            modal.classList.remove('hidden');
        } else {
            // Closing modal
            modal.classList.add('hidden');
        }
    };

    // Function to close the modal
    window.closeModal = function() {
        modal.classList.add('hidden');
    };

    // Client-side validation
    if (transactionForm) {
        transactionForm.addEventListener('submit', function(e) {
            const amount = parseFloat(document.getElementById('modalAmount').value);
            const date = document.getElementById('modalTransactionDate').value;
            const today = new Date().toISOString().slice(0, 10);
            const type = document.getElementById('modalType').value;

            if (!type) {
                e.preventDefault();
                alert('Please select a transaction type (Income or Expense).');
                return;
            }

            if (amount <= 0 || isNaN(amount)) {
                e.preventDefault();
                alert('Amount must be greater than zero.');
                return;
            }

            if (date > today) {
                e.preventDefault();
                alert('Transaction date cannot be in the future.');
                return;
            }
        });
    }

    // Function to fill preset transaction data
    window.fillPresetTransaction = function(type, amount, category, description) {
        setTransactionType(type);
        document.getElementById('modalAmount').value = amount;
        document.getElementById('modalCategory').value = category;
        document.getElementById('modalDescription').value = description;
        document.getElementById('modalTransactionDate').value = new Date().toISOString().slice(0, 10);
        
        // Focus on amount field for easy editing
        setTimeout(() => {
            const amountField = document.getElementById('modalAmount');
            amountField.focus();
            amountField.select();
        }, 100);
    };

    // Close modal when clicking outside
    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                closeModal();
            }
        });
    }

    // Close modal with Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && !modal.classList.contains('hidden')) {
            closeModal();
        }
    });
});
