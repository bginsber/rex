// ============================================
// RexLit - Interactive Behaviors
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    initSearchModeToggle();
    initKeyboardShortcuts();
    initDocumentCards();
    initNavigation();
    initAnimations();
});

// ============================================
// Search Mode Toggle (GUI/CLI)
// ============================================

function initSearchModeToggle() {
    const toggle = document.getElementById('searchModeToggle');
    const guiMode = document.querySelector('.search-container.gui-mode');
    const cliMode = document.querySelector('.search-container.cli-mode');

    if (!toggle || !guiMode || !cliMode) return;

    toggle.addEventListener('click', () => {
        const isCliActive = toggle.classList.contains('cli-active');

        if (isCliActive) {
            // Switch to GUI
            toggle.classList.remove('cli-active');
            guiMode.style.display = 'block';
            cliMode.style.display = 'none';
            toggle.querySelector('.mode-label:first-child').style.color = 'var(--cyan-500)';
            toggle.querySelector('.mode-label:last-child').style.color = 'var(--text-tertiary)';
        } else {
            // Switch to CLI
            toggle.classList.add('cli-active');
            guiMode.style.display = 'none';
            cliMode.style.display = 'block';
            toggle.querySelector('.mode-label:first-child').style.color = 'var(--text-tertiary)';
            toggle.querySelector('.mode-label:last-child').style.color = 'var(--cyan-500)';

            // Focus the terminal input
            const terminalInput = cliMode.querySelector('.terminal-input');
            if (terminalInput) {
                setTimeout(() => terminalInput.focus(), 100);
            }
        }
    });
}

// ============================================
// Keyboard Shortcuts
// ============================================

function initKeyboardShortcuts() {
    const shortcutsOverlay = document.getElementById('shortcutsOverlay');

    // Helper to check if focus is on an interactive control
    const isFocusOnControl = () => {
        const activeElement = document.activeElement;
        if (!activeElement) return false;

        // Check for input fields
        const tagName = activeElement.tagName;
        if (tagName === 'INPUT' || tagName === 'TEXTAREA' || tagName === 'SELECT') {
            return true;
        }

        // Check for buttons and other interactive elements
        if (tagName === 'BUTTON' || activeElement.hasAttribute('contenteditable')) {
            return true;
        }

        // Check for elements with interactive roles
        const role = activeElement.getAttribute('role');
        if (role === 'button' || role === 'textbox' || role === 'combobox') {
            return true;
        }

        return false;
    };

    document.addEventListener('keydown', (e) => {
        const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
        const modKey = isMac ? e.metaKey : e.ctrlKey;

        // ⌘/Ctrl + K: Focus search
        if (modKey && e.key === 'k') {
            e.preventDefault();
            const searchInput = document.querySelector('.search-input');
            if (searchInput) searchInput.focus();
        }

        // ⌘/Ctrl + /: Toggle search mode
        if (modKey && e.key === '/') {
            e.preventDefault();
            const toggle = document.getElementById('searchModeToggle');
            if (toggle) toggle.click();
        }

        // ?: Show keyboard shortcuts
        if (e.key === '?' && !e.metaKey && !e.ctrlKey && !e.altKey) {
            if (!isFocusOnControl() && shortcutsOverlay) {
                e.preventDefault();
                shortcutsOverlay.style.display = 'flex';
            }
        }

        // Escape: Close overlays
        if (e.key === 'Escape') {
            if (shortcutsOverlay && shortcutsOverlay.style.display === 'flex') {
                shortcutsOverlay.style.display = 'none';
            }
        }

        // J/K: Navigate documents (Vim-style)
        if ((e.key === 'j' || e.key === 'k') && !e.metaKey && !e.ctrlKey) {
            if (!isFocusOnControl()) {
                e.preventDefault();
                navigateDocuments(e.key === 'j' ? 'next' : 'prev');
            }
        }

        // P: Mark as privileged
        if (e.key === 'p' && !e.metaKey && !e.ctrlKey) {
            if (!isFocusOnControl()) {
                e.preventDefault();
                markClassification('privileged');
            }
        }

        // R: Mark as responsive
        if (e.key === 'r' && !e.metaKey && !e.ctrlKey) {
            if (!isFocusOnControl()) {
                e.preventDefault();
                markClassification('responsive');
            }
        }

        // X: Mark for production
        if (e.key === 'x' && !e.metaKey && !e.ctrlKey) {
            if (!isFocusOnControl()) {
                e.preventDefault();
                markClassification('production');
            }
        }
    });

    // Close overlay when clicking outside
    if (shortcutsOverlay) {
        shortcutsOverlay.addEventListener('click', (e) => {
            if (e.target === shortcutsOverlay) {
                shortcutsOverlay.style.display = 'none';
            }
        });
    }
}

// ============================================
// Document Card Interactions
// ============================================

function initDocumentCards() {
    const cards = document.querySelectorAll('.document-card');

    cards.forEach(card => {
        card.addEventListener('click', () => {
            // Remove active state and clear transforms from all cards
            cards.forEach(c => {
                c.classList.remove('active');
                c.style.transform = ''; // Clear any inline transform
            });

            // Add active state to clicked card
            card.classList.add('active');

            // Animate transition (you could load actual document here)
            animateDocumentTransition();
        });

        // Add hover sound effect (subtle UI feedback)
        card.addEventListener('mouseenter', () => {
            card.style.transform = 'translateX(4px)';
        });

        card.addEventListener('mouseleave', () => {
            if (!card.classList.contains('active')) {
                card.style.transform = '';
            }
        });
    });
}

function navigateDocuments(direction) {
    const cards = Array.from(document.querySelectorAll('.document-card'));
    const activeCard = document.querySelector('.document-card.active');

    if (cards.length === 0) return;

    let currentIndex = activeCard ? cards.indexOf(activeCard) : -1;
    let nextIndex;

    if (direction === 'next') {
        nextIndex = currentIndex < cards.length - 1 ? currentIndex + 1 : 0;
    } else {
        nextIndex = currentIndex > 0 ? currentIndex - 1 : cards.length - 1;
    }

    // Remove active state and clear transforms from all cards
    cards.forEach(c => {
        c.classList.remove('active');
        c.style.transform = ''; // Clear any inline transform
    });
    cards[nextIndex].classList.add('active');

    // Scroll into view
    cards[nextIndex].scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    animateDocumentTransition();
}

function markClassification(type) {
    const activeCard = document.querySelector('.document-card.active');
    if (!activeCard) return;

    // Remove existing classification classes
    activeCard.classList.remove('privileged', 'responsive', 'production');

    // Add new classification
    activeCard.classList.add(type);

    // Update badge
    const badge = activeCard.querySelector('.privilege-badge');
    if (badge) {
        badge.className = 'privilege-badge';

        switch(type) {
            case 'privileged':
                badge.classList.add('glow');
                badge.innerHTML = `
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                        <path d="M6 1L2 4V7C2 9 6 10.5 6 10.5C6 10.5 10 9 10 7V4L6 1Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
                    </svg>
                    PRIVILEGED
                `;
                break;
            case 'responsive':
                badge.classList.add('responsive-badge');
                badge.textContent = 'RESPONSIVE';
                break;
            case 'production':
                badge.classList.add('production-badge');
                badge.textContent = 'PRODUCTION';
                break;
        }
    }

    // Show feedback
    showToast(`Marked as ${type.toUpperCase()}`);
}

// ============================================
// Navigation
// ============================================

function initNavigation() {
    const navItems = document.querySelectorAll('.nav-item');

    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const view = item.dataset.view;

            // Update active state
            navItems.forEach(n => n.classList.remove('active'));
            item.classList.add('active');

            // In a real app, this would switch views
            console.log(`Switching to ${view} view`);
            showToast(`${view.charAt(0).toUpperCase() + view.slice(1)} view`);
        });
    });
}

// ============================================
// Animations
// ============================================

function initAnimations() {
    // Observe elements entering viewport
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);

    // Observe all document cards
    const cards = document.querySelectorAll('.document-card');
    cards.forEach(card => observer.observe(card));
}

function animateDocumentTransition() {
    const viewer = document.querySelector('.document-preview');
    if (!viewer) return;

    // Subtle fade animation
    viewer.style.opacity = '0.5';
    viewer.style.transform = 'translateY(10px)';

    setTimeout(() => {
        viewer.style.transition = 'opacity 300ms, transform 300ms';
        viewer.style.opacity = '1';
        viewer.style.transform = 'translateY(0)';
    }, 50);
}

// ============================================
// Toast Notifications
// ============================================

function showToast(message) {
    // Remove existing toast
    const existingToast = document.querySelector('.toast');
    if (existingToast) {
        existingToast.remove();
    }

    // Create toast
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;

    // Style toast
    Object.assign(toast.style, {
        position: 'fixed',
        bottom: '24px',
        right: '24px',
        padding: '12px 24px',
        background: 'var(--bg-elevated)',
        border: '1px solid var(--amber-500)',
        borderRadius: '6px',
        color: 'var(--amber-500)',
        fontFamily: 'var(--font-mono)',
        fontSize: '12px',
        fontWeight: '600',
        zIndex: '10000',
        boxShadow: '0 0 20px rgba(232, 183, 106, 0.3)',
        animation: 'slideInUp 300ms cubic-bezier(0.4, 0, 0.2, 1)',
        textTransform: 'uppercase',
        letterSpacing: '0.5px'
    });

    document.body.appendChild(toast);

    // Remove after 2 seconds
    setTimeout(() => {
        toast.style.animation = 'slideOutDown 300ms cubic-bezier(0.4, 0, 0.2, 1)';
        setTimeout(() => toast.remove(), 300);
    }, 2000);
}

// Add toast animations to stylesheet
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInUp {
        from {
            opacity: 0;
            transform: translateY(20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    @keyframes slideOutDown {
        from {
            opacity: 1;
            transform: translateY(0);
        }
        to {
            opacity: 0;
            transform: translateY(20px);
        }
    }
`;
document.head.appendChild(style);

// ============================================
// CLI Terminal Enhancements
// ============================================

// Add command history for terminal
let commandHistory = [];
let historyIndex = -1;

const terminalInput = document.querySelector('.terminal-input');
if (terminalInput) {
    terminalInput.addEventListener('keydown', (e) => {
        // Up arrow: previous command
        if (e.key === 'ArrowUp') {
            e.preventDefault();
            if (historyIndex < commandHistory.length - 1) {
                historyIndex++;
                terminalInput.value = commandHistory[historyIndex];
            }
        }

        // Down arrow: next command
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (historyIndex > 0) {
                historyIndex--;
                terminalInput.value = commandHistory[historyIndex];
            } else if (historyIndex === 0) {
                historyIndex = -1;
                terminalInput.value = '';
            }
        }

        // Enter: execute command
        if (e.key === 'Enter') {
            const command = terminalInput.value.trim();
            if (command) {
                commandHistory.unshift(command);
                historyIndex = -1;

                // In a real app, this would execute the command
                console.log('Executing command:', command);
                showToast('Command executed');
            }
        }
    });
}

// ============================================
// Filter Pills Interaction
// ============================================

const filterPills = document.querySelectorAll('.pill');
filterPills.forEach(pill => {
    pill.addEventListener('click', () => {
        const isActive = pill.classList.toggle('active');

        // Update aria-pressed to match active state for accessibility
        pill.setAttribute('aria-pressed', isActive.toString());

        // Get active filters
        const activeFilters = Array.from(filterPills)
            .filter(p => p.classList.contains('active'))
            .map(p => p.textContent);

        console.log('Active filters:', activeFilters);
    });
});

// ============================================
// Status Bar Enhancements
// ============================================

// Update Bates counter in real-time (simulated)
function updateBatesCounter() {
    const counter = document.querySelector('.bates-counter .mono');
    if (!counter) return;

    let currentNumber = 428391;

    setInterval(() => {
        // Simulate occasional updates
        if (Math.random() > 0.95) {
            currentNumber++;
            const newBates = `APEX-${String(currentNumber).padStart(8, '0')}`;
            counter.textContent = newBates;

            // Briefly highlight the change
            counter.style.color = 'var(--cyan-500)';
            setTimeout(() => {
                counter.style.color = 'var(--amber-500)';
            }, 1000);
        }
    }, 5000);
}

updateBatesCounter();

console.log('🎯 RexLit initialized');
console.log('💡 Press ? for keyboard shortcuts');
