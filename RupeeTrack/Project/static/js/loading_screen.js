document.addEventListener('DOMContentLoaded', function() {
    const loadingOverlay = document.getElementById('loading-overlay');
    if (!loadingOverlay) {
        console.error("Loading overlay element not found!");
        return;
    }

    const hasVisited = sessionStorage.getItem('hasVisited');

    if (!hasVisited) {
        // First visit in a session: keep loading screen visible for a delay
        setTimeout(() => {
            loadingOverlay.classList.add('hidden');
            loadingOverlay.addEventListener('transitionend', () => {
                loadingOverlay.style.display = 'none'; // Fully hide after transition
            }, { once: true });
        }, 2500); // 2.5 seconds delay for loading screen
        sessionStorage.setItem('hasVisited', 'true');
    } else {
        // Subsequent visits: immediately hide loading screen
        loadingOverlay.classList.add('hidden');
        loadingOverlay.style.display = 'none'; // Ensure it's hidden instantly
    }

    // Function to show loading screen manually (e.g., on logo click)
    window.showLoadingScreen = function() {
        if (loadingOverlay) {
            loadingOverlay.style.display = 'flex'; // Show it
            loadingOverlay.classList.remove('hidden'); // Remove hidden class to allow transition
            
            setTimeout(() => {
                loadingOverlay.classList.add('hidden');
                loadingOverlay.addEventListener('transitionend', () => {
                    loadingOverlay.style.display = 'none';
                }, { once: true });
            }, 2500); // 2.5 seconds delay for loading screen
        }
    };
});
