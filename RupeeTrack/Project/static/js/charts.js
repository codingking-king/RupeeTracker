document.addEventListener('DOMContentLoaded', function() {
    // Function to parse JSON data from a script tag
    function getChartData(id) {
        const scriptTag = document.getElementById(id);
        if (scriptTag && scriptTag.textContent) {
            try {
                return JSON.parse(scriptTag.textContent);
            } catch (e) {
                console.error(`Error parsing JSON from script tag ${id}:`, e);
                return null;
            }
        }
        return null;
    }

    // Get data from the hidden script tags in dashboard.html
    const monthlySummaryData = getChartData('monthly-summary-data');
    const expenseBreakdownData = getChartData('expense-breakdown-data');
    const cashFlowData = getChartData('cash-flow-data');
    const dailySummaryData = getChartData('daily-summary-data');

    // Define a fixed set of colors for the pie chart
    const fixedPieColors = [
        'rgba(255, 99, 132, 0.7)',  // Red
        'rgba(54, 162, 235, 0.7)',  // Blue
        'rgba(255, 206, 86, 0.7)',  // Yellow
        'rgba(75, 192, 192, 0.7)',  // Green
        'rgba(153, 102, 255, 0.7)', // Purple
        'rgba(255, 159, 64, 0.7)',  // Orange
        'rgba(199, 199, 199, 0.7)', // Grey
        'rgba(83, 102, 255, 0.7)',  // Indigo
        'rgba(233, 30, 99, 0.7)',   // Pink
        'rgba(0, 150, 136, 0.7)'    // Teal
    ];

    // 1. Render Income vs. Expense Over Time Chart (Line Chart)
    if (monthlySummaryData) {
        const ctx = document.getElementById('incomeExpenseChart').getContext('2d');
        const labels = Object.keys(monthlySummaryData).map(monthYear => {
            const [year, month] = monthYear.split('-');
            const date = new Date(year, month - 1);
            return date.toLocaleString('default', { month: 'short', year: '2-digit' });
        });
        const incomes = Object.values(monthlySummaryData).map(data => data.income);
        const expenses = Object.values(monthlySummaryData).map(data => data.expense);

        new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Income',
                        data: incomes,
                        borderColor: 'rgba(16, 185, 129, 1)', // accent-500
                        backgroundColor: 'rgba(16, 185, 129, 0.2)',
                        fill: true,
                        tension: 0.3
                    },
                    {
                        label: 'Expenses',
                        data: expenses,
                        borderColor: 'rgba(239, 68, 68, 1)', // red-500
                        backgroundColor: 'rgba(239, 68, 68, 0.2)',
                        fill: true,
                        tension: 0.3
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: false,
                        text: 'Income vs. Expense Over Time'
                    },
                    legend: {
                        labels: {
                            color: 'rgb(243, 244, 246)' // text-dark
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            color: 'rgb(209, 213, 219)' // dark-300
                        },
                        grid: {
                            color: 'rgba(55, 65, 81, 0.5)' // dark-700 with opacity
                        }
                    },
                    y: {
                        beginAtZero: true,
                        ticks: {
                            color: 'rgb(209, 213, 219)', // dark-300
                            callback: function(value) {
                                return '₹' + value.toLocaleString('en-IN');
                            }
                        },
                        grid: {
                            color: 'rgba(55, 65, 81, 0.5)' // dark-700 with opacity
                        }
                    }
                }
            }
        });
    }

    // 2. Render Monthly Expense Breakdown (Horizontal Bar Chart)
    if (expenseBreakdownData && Object.keys(expenseBreakdownData).length > 0) {
        const ctx = document.getElementById('expenseBreakdownChart').getContext('2d');
        const labels = Object.keys(expenseBreakdownData);
        const data = Object.values(expenseBreakdownData);
        // Use fixed colors, cycling through them if there are more categories than colors
        const backgroundColors = labels.map((_, i) => fixedPieColors[i % fixedPieColors.length]);

        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Amount',
                    data: data,
                    backgroundColor: backgroundColors,
                    borderColor: backgroundColors.map(color => color.replace('0.7', '1')), // Darker border
                    borderWidth: 1
                }]
            },
            options: {
                indexAxis: 'y', // This makes it a horizontal bar chart
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: false,
                        text: 'Monthly Expense Breakdown'
                    },
                    legend: {
                        display: false // Hide legend for cleaner look
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        ticks: {
                            color: 'rgb(209, 213, 219)', // dark-300
                            callback: function(value) {
                                return '₹' + value.toLocaleString('en-IN');
                            }
                        },
                        grid: {
                            color: 'rgba(55, 65, 81, 0.5)' // dark-700 with opacity
                        }
                    },
                    y: {
                        ticks: {
                            color: 'rgb(209, 213, 219)' // dark-300
                        },
                        grid: {
                            color: 'rgba(55, 65, 81, 0.5)' // dark-700 with opacity
                        }
                    }
                }
            }
        });
    } else {
        // Display a message if no expense data
        const container = document.getElementById('expenseBreakdownChart').parentNode;
        container.innerHTML = `
            <h2 class="text-lg md:text-xl font-semibold text-text-dark mb-3 md:mb-4">Monthly Expense Breakdown</h2>
            <div class="text-center text-gray-400 py-8">No expense data available for this month.</div>
        `;
    }

    // 3. Render Monthly Cash Flow (Bar Chart)
    if (cashFlowData) {
        const ctx = document.getElementById('cashFlowChart').getContext('2d');
        const labels = Object.keys(cashFlowData).map(monthYear => {
            const [year, month] = monthYear.split('-');
            const date = new Date(year, month - 1);
            return date.toLocaleString('default', { month: 'short', year: '2-digit' });
        });
        const data = Object.values(cashFlowData);

        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Net Cash Flow',
                    data: data,
                    backgroundColor: data.map(value => value >= 0 ? 'rgba(16, 185, 129, 0.7)' : 'rgba(239, 68, 68, 0.7)'), // Green for positive, Red for negative
                    borderColor: data.map(value => value >= 0 ? 'rgba(16, 185, 129, 1)' : 'rgba(239, 68, 68, 1)'),
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: false,
                        text: 'Monthly Cash Flow'
                    },
                    legend: {
                        display: false
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            color: 'rgb(209, 213, 219)' // dark-300
                        },
                        grid: {
                            color: 'rgba(55, 65, 81, 0.5)' // dark-700 with opacity
                        }
                    },
                    y: {
                        beginAtZero: false, // Allow negative values
                        ticks: {
                            color: 'rgb(209, 213, 219)', // dark-300
                            callback: function(value) {
                                return '₹' + value.toLocaleString('en-IN');
                            }
                        },
                        grid: {
                            color: 'rgba(55, 65, 81, 0.5)' // dark-700 with opacity
                        }
                    }
                }
            }
        });
    } else {
        // Display a message if no cash flow data
        const container = document.getElementById('cashFlowChart').parentNode;
        container.innerHTML = `
            <h2 class="text-lg md:text-xl font-semibold text-text-dark mb-3 md:mb-4">Monthly Cash Flow</h2>
            <div class="text-center text-gray-400 py-8">No cash flow data available.</div>
        `;
    }

    // 4. Render Daily Income vs. Expense (Line Chart)
    if (dailySummaryData) {
        const ctx = document.getElementById('dailyIncomeExpenseChart').getContext('2d');
        const labels = Object.keys(dailySummaryData).map(dateStr => {
            const date = new Date(dateStr);
            return date.toLocaleString('default', { day: 'numeric', month: 'short' });
        });
        const incomes = Object.values(dailySummaryData).map(data => data.income);
        const expenses = Object.values(dailySummaryData).map(data => data.expense);

        new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Daily Income',
                        data: incomes,
                        borderColor: 'rgba(16, 185, 129, 1)', // accent-500
                        backgroundColor: 'rgba(16, 185, 129, 0.2)',
                        fill: true,
                        tension: 0.3
                    },
                    {
                        label: 'Daily Expenses',
                        data: expenses,
                        borderColor: 'rgba(239, 68, 68, 1)', // red-500
                        backgroundColor: 'rgba(239, 68, 68, 0.2)',
                        fill: true,
                        tension: 0.3
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: false,
                        text: 'Daily Income vs. Expense'
                    },
                    legend: {
                        labels: {
                            color: 'rgb(243, 244, 246)' // text-dark
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            color: 'rgb(209, 213, 219)' // dark-300
                        },
                        grid: {
                            color: 'rgba(55, 65, 81, 0.5)' // dark-700 with opacity
                        }
                    },
                    y: {
                        beginAtZero: false, // Allow dynamic scaling based on data
                        ticks: {
                            color: 'rgb(209, 213, 219)', // dark-300
                            callback: function(value) {
                                return '₹' + value.toLocaleString('en-IN');
                            }
                        },
                        grid: {
                            color: 'rgba(55, 65, 81, 0.5)' // dark-700 with opacity
                        }
                    }
                }
            }
        });
    } else {
        // Display a message if no daily data
        const container = document.getElementById('dailyIncomeExpenseChart').parentNode;
        container.innerHTML = `
            <h2 class="text-lg md:text-xl font-semibold text-text-dark mb-3 md:mb-4">Daily Income vs. Expense</h2>
            <div class="text-center text-gray-400 py-8">No daily transaction data available for the last 30 days.</div>
        `;
    }
});
