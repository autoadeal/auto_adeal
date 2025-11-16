// Global Variables
let cartItems = [];
let wishlistItems = [];
let currentUser = null;

// ============================================
// CART & WISHLIST MANAGEMENT
// ============================================
function loadCartFromStorage() {
    try {
        const stored = localStorage.getItem('auto_adeal_cart');
        if (stored) cartItems = JSON.parse(stored);
    } catch (e) {
        cartItems = [];
    }
}

function saveCartToStorage() {
    localStorage.setItem('auto_adeal_cart', JSON.stringify(cartItems));
}

function loadWishlistFromStorage() {
    try {
        const stored = localStorage.getItem('auto_adeal_wishlist');
        if (stored) wishlistItems = JSON.parse(stored);
    } catch (e) {
        wishlistItems = [];
    }
}

function saveWishlistToStorage() {
    localStorage.setItem('auto_adeal_wishlist', JSON.stringify(wishlistItems));
}

function updateCartCount() {
    const count = cartItems.length;
    const cartCount = document.getElementById('cart-count');
    const cartCountMobile = document.getElementById('cart-count-mobile');
    if (cartCount) cartCount.textContent = count;
    if (cartCountMobile) cartCountMobile.textContent = count;
}

function updateWishlistCount() {
    const count = wishlistItems.length;
    const wishlistCount = document.getElementById('wishlist-count');
    const wishlistCountMobile = document.getElementById('wishlist-count-mobile');
    if (wishlistCount) wishlistCount.textContent = count;
    if (wishlistCountMobile) wishlistCountMobile.textContent = count;
}

// ============================================
// USER AUTHENTICATION
// ============================================
function loadUserFromStorage() {
    const stored = localStorage.getItem('auto_adeal_user');
    const loginTime = localStorage.getItem('auto_adeal_login_time');
    
    if (stored && loginTime) {
        const daysSinceLogin = (Date.now() - parseInt(loginTime)) / (1000 * 60 * 60 * 24);
        
        if (daysSinceLogin < 730) {
            try {
                currentUser = JSON.parse(stored);
                updateAuthUI();
            } catch (e) {
                localStorage.removeItem('auto_adeal_user');
                localStorage.removeItem('auto_adeal_login_time');
            }
        } else {
            localStorage.removeItem('auto_adeal_user');
            localStorage.removeItem('auto_adeal_login_time');
        }
    }
}

function saveUserToStorage(user) {
    localStorage.setItem('auto_adeal_user', JSON.stringify(user));
    localStorage.setItem('auto_adeal_login_time', Date.now().toString());
}

function updateAuthUI() {
    const accountLabel = document.getElementById('account-label');
    const loggedOutOptions = document.getElementById('logged-out-options');
    const loggedInOptions = document.getElementById('logged-in-options');
    const dropdownUserName = document.getElementById('dropdown-user-name');
    const dropdownUserEmail = document.getElementById('dropdown-user-email');
    
    const loggedOutOptionsMobile = document.getElementById('logged-out-options-mobile');
    const loggedInOptionsMobile = document.getElementById('logged-in-options-mobile');
    const dropdownUserNameMobile = document.getElementById('dropdown-user-name-mobile');
    const dropdownUserEmailMobile = document.getElementById('dropdown-user-email-mobile');
    
    if (currentUser) {
        if (accountLabel) accountLabel.textContent = currentUser.name;
        if (loggedOutOptions) loggedOutOptions.classList.add('hidden');
        if (loggedInOptions) loggedInOptions.classList.remove('hidden');
        if (dropdownUserName) dropdownUserName.textContent = `${currentUser.name} ${currentUser.surname}`;
        if (dropdownUserEmail) dropdownUserEmail.textContent = currentUser.email;
        
        if (loggedOutOptionsMobile) loggedOutOptionsMobile.classList.add('hidden');
        if (loggedInOptionsMobile) loggedInOptionsMobile.classList.remove('hidden');
        if (dropdownUserNameMobile) dropdownUserNameMobile.textContent = `${currentUser.name} ${currentUser.surname}`;
        if (dropdownUserEmailMobile) dropdownUserEmailMobile.textContent = currentUser.email;
    } else {
        if (accountLabel) accountLabel.textContent = 'Llogaria';
        if (loggedOutOptions) loggedOutOptions.classList.remove('hidden');
        if (loggedInOptions) loggedInOptions.classList.add('hidden');
        
        if (loggedOutOptionsMobile) loggedOutOptionsMobile.classList.remove('hidden');
        if (loggedInOptionsMobile) loggedInOptionsMobile.classList.add('hidden');
    }
}

function toggleAccountDropdown() {
    const dropdown = document.getElementById('account-dropdown');
    const dropdownMobile = document.getElementById('account-dropdown-mobile');
    if (dropdown) dropdown.classList.toggle('hidden');
    if (dropdownMobile) dropdownMobile.classList.toggle('hidden');
}
    
function closeAccountDropdown() {
    const dropdown = document.getElementById('account-dropdown');
    const dropdownMobile = document.getElementById('account-dropdown-mobile');
    if (dropdown) dropdown.classList.add('hidden');
    if (dropdownMobile) dropdownMobile.classList.add('hidden');
}

function showLoginModal() {
    document.getElementById('auth-modal').style.display = 'flex';
    document.getElementById('auth-title').textContent = 'Hyr';
    document.getElementById('login-form').style.display = 'block';
    document.getElementById('signup-form').style.display = 'none';
    document.getElementById('forgot-form').style.display = 'none';
}

function showSignupModal() {
    document.getElementById('auth-modal').style.display = 'flex';
    document.getElementById('auth-title').textContent = 'Regjistrohu';
    document.getElementById('login-form').style.display = 'none';
    document.getElementById('signup-form').style.display = 'block';
    document.getElementById('forgot-form').style.display = 'none';
}

function closeAuthModal() {
    document.getElementById('auth-modal').style.display = 'none';
    document.getElementById('login-form').reset();
    document.getElementById('signup-form').reset();
    document.getElementById('forgot-form').reset();
}

function showLoginForm() {
    showLoginModal();
}

function showSignupForm() {
    showSignupModal();
}

function showForgotPassword() {
    document.getElementById('auth-title').textContent = 'Rivendos fjalëkalimin';
    document.getElementById('login-form').style.display = 'none';
    document.getElementById('signup-form').style.display = 'none';
    document.getElementById('forgot-form').style.display = 'block';
}

async function handleLogin(event) {
    event.preventDefault();
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;

    try {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            currentUser = data.user;
            saveUserToStorage(data.user);
            updateAuthUI();
            closeAuthModal();
            showNotification('Hyra u krye me sukses!', 'success');
        } else {
            showNotification(data.error || 'Hyra dështoi', 'error');
        }
    } catch (error) {
        showNotification('Hyra dështoi. Provoni përsëri.', 'error');
    }
}

async function handleSignup(event) {
    event.preventDefault();
    const name = document.getElementById('signup-name').value;
    const surname = document.getElementById('signup-surname').value;
    const email = document.getElementById('signup-email').value;
    const password = document.getElementById('signup-password').value;

    try {
        const response = await fetch('/api/auth/signup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, surname, email, password })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            currentUser = data.user;
            saveUserToStorage(data.user);
            updateAuthUI();
            closeAuthModal();
            showNotification('Llogaria u krijua me sukses!', 'success');
        } else {
            showNotification(data.error || 'Regjistrimi dështoi', 'error');
        }
    } catch (error) {
        showNotification('Regjistrimi dështoi. Provoni përsëri.', 'error');
    }
}

async function handleForgotPassword(event) {
    event.preventDefault();
    const email = document.getElementById('forgot-email').value;

    try {
        const response = await fetch('/api/auth/forgot-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showNotification('Link për rikthimin e fjalëkalimit u dërgua në email', 'success');
            closeAuthModal();
        } else {
            showNotification(data.error || 'Kerkesa deshtoi', 'error');
        }
    } catch (error) {
        showNotification('Kerkesa deshtoi', 'error');
    }
}

function logout() {
    currentUser = null;
    localStorage.removeItem('auto_adeal_user');
    localStorage.removeItem('auto_adeal_login_time');
    updateAuthUI();
    showNotification('Dalja u krye me sukses', 'success');
    }
    // ============================================
    // UTILITY FUNCTIONS
    // ============================================
    function showNotification(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = fixed top-4 right-4 ${type === 'success' ? 'bg-green-600' : 'bg-red-600'} text-white px-6 py-3 rounded-lg shadow-lg z-50;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ============================================
// SCROLL TO TOP BUTTON
// ============================================
function initScrollButton() {
    const scrollBtn = document.getElementById('scroll-to-top-btn');
    if (!scrollBtn) return;
        window.addEventListener('scroll', function() {
            if (window.scrollY > 300) {
                scrollBtn.classList.add('visible');
            } else {
                scrollBtn.classList.remove('visible');
            }
        }, { passive: true });

        scrollBtn.addEventListener('click', function() {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
}

// ============================================
// CLOSE DROPDOWN WHEN CLICKING OUTSIDE
// ============================================
document.addEventListener('click', function(event) {
const accountButton = document.getElementById('account-button');
const accountButtonMobile = document.getElementById('account-button-mobile');
const dropdown = document.getElementById('account-dropdown');
const dropdownMobile = document.getElementById('account-dropdown-mobile');
const clickedAccountButton = accountButton && accountButton.contains(event.target);
const clickedAccountButtonMobile = accountButtonMobile && accountButtonMobile.contains(event.target);
const clickedDropdown = dropdown && dropdown.contains(event.target);
const clickedDropdownMobile = dropdownMobile && dropdownMobile.contains(event.target);

    if (!clickedAccountButton && !clickedAccountButtonMobile && !clickedDropdown && !clickedDropdownMobile) {
        if (dropdown) dropdown.classList.add('hidden');
        if (dropdownMobile) dropdownMobile.classList.add('hidden');
    }
});

// ============================================
// INITIALIZATION
// ============================================
document.addEventListener('DOMContentLoaded', function() {
loadCartFromStorage();
loadWishlistFromStorage();
loadUserFromStorage();
updateCartCount();
updateWishlistCount();
initScrollButton();
});