document.addEventListener('DOMContentLoaded', function() {
    // Charts are now initialized directly in dashboard.html using Jinja2 variables.
    // This file will no longer handle chart initialization.

    // Filter Transactions Logic (assuming transactionsData is still available globally or passed differently)
    // If transactionsData is no longer globally available, this section will need to be updated.
    // For now, assuming it's passed via a script tag with ID 'transactions-data' or similar.
    const transactionsDataElement = document.getElementById('transactions-data');
    const transactionsData = transactionsDataElement ? JSON.parse(transactionsDataElement.textContent) : [];

    const monthFilter = document.getElementById('monthFilter');
    const typeFilter = document.getElementById('typeFilter');
    const startDateInput = document.getElementById('startDate');
    const endDateInput = document.getElementById('endDate');
    const applyFiltersButton = document.getElementById('applyFilters');
    const transactionTableBody = document.querySelector('.transaction-table tbody');

    function applyFilters() {
        const selectedMonth = monthFilter.value;
        const selectedType = typeFilter.value;
        const startDate = startDateInput.value ? new Date(startDateInput.value) : null;
        const endDate = endDateInput.value ? new Date(endDateInput.value) : null;

        const filteredTransactions = transactionsData.filter(transaction => {
            const transactionDate = new Date(transaction.timestamp);
            const transactionMonth = (transactionDate.getMonth() + 1).toString().padStart(2, '0');

            const monthMatch = !selectedMonth || transactionMonth === selectedMonth;
            const typeMatch = !selectedType || transaction.type.toLowerCase() === selectedType;
            const dateMatch = (!startDate || transactionDate >= startDate) && (!endDate || transactionDate <= endDate);

            return monthMatch && typeMatch && dateMatch;
        });

        renderTransactions(filteredTransactions);
    }

    function renderTransactions(transactions) {
        transactionTableBody.innerHTML = ''; // Clear existing rows

        if (transactions.length === 0) {
            const noTransactionsRow = document.createElement('tr');
            noTransactionsRow.innerHTML = `<td colspan="6" style="text-align: center; padding: 20px;">No transactions found.</td>`;
            transactionTableBody.appendChild(noTransactionsRow);
            return;
        }

        transactions.forEach(transaction => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${new Date(transaction.timestamp).toLocaleString('en-US', { month: 'short', day: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: true })}</td>
                <td>${transaction.description}</td>
                <td>${transaction.category}</td>
                <td class="type-${transaction.type.toLowerCase()}">${transaction.type}</td>
                <td>$${transaction.amount.toFixed(2)}</td>
                <td>
                    <button class="action-button edit-button" onclick="location.href='/edit_transaction/${transaction.id}'"><i class="fas fa-edit"></i></button>
                    <button class="action-button delete-button" onclick="location.href='/delete_transaction/${transaction.id}'"><i class="fas fa-trash-alt"></i></button>
                </td>
            `;
            transactionTableBody.appendChild(row);
        });
    }

    applyFiltersButton.addEventListener('click', applyFilters);

    // Initial render of transactions
    renderTransactions(transactionsData);
});
