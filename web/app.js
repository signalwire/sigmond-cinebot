// SignalWire WebRTC Configuration
const STATIC_TOKEN = 'eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2R0NNIiwidHlwIjoiU0FUIiwiY2giOiJwdWMuc2lnbmFsd2lyZS5jb20ifQ..arsTAToqHlmZIcfC.5iqzbQj5ojJlZjzKqkM1NjwX2W8XpBIVgV0R6f4irFqMuv6HWwLviXga9XoK7PAA5zeNIJtNzbAhqzwfL2vAnp8rdfj4g5beRWDs8p0pNnII7KNwC1RJ4vDAI_0chSnvngMeQ901AgxqGQ6RnoKq-fqzq-Fexq9B--lD-SRUth2U57FkQZWO6ae3O5EyaqC5G6Is7x6Lr-vXt-h6fHltriAemODYo5aVBoVMVxZc-qXd0I6sSUkuLcokd6iUoM5IPW9z-9YwjFMVV--eO0fhyYCKroR_j4kZWfgPIVNrhr4hLBwhUlGcTF4gdqcSXse7gCr74EzZSueXf-a-DooYoj_p4cYXTxh6mZSNMsg1ptDdoYUS41-NlRTsenNzbGuT5_K62eX59igL_W8VPdZ1P_bXy0ezkj_05XbUGO9P4TgOSEoBZ0Eobma_M0hFJwECkhXylrjv1WGVCseQ6-NyYX--J0o8bNs-UHpbbhNkOy1tJvn7KtT8IQZ0ud4OhgtP_V1wGC58O8b4zmTMTbCTYRRqLY65wS8bLH0mhSKM.yf0tegw6KLIb-QoPDssk-Q';
const DESTINATION = '/public/cinebot';

// Global state
let client = null;
let roomSession = null;
let isContentDisplayed = false;

// UI Elements - will be initialized after DOM loads
let elements = {};

// Placeholder images as data URLs (URL encoded to handle Unicode)
const PLACEHOLDER_POSTER = 'data:image/svg+xml,' + encodeURIComponent(`
<svg width="200" height="300" xmlns="http://www.w3.org/2000/svg">
  <rect width="200" height="300" fill="#1a1a1a"/>
  <rect x="60" y="110" width="80" height="80" fill="#333" rx="5"/>
  <circle cx="100" cy="150" r="25" fill="none" stroke="#555" stroke-width="3"/>
  <rect x="50" y="140" width="100" height="20" fill="#333"/>
  <rect x="70" y="125" width="10" height="10" fill="#555"/>
  <rect x="120" y="125" width="10" height="10" fill="#555"/>
</svg>`);

const PLACEHOLDER_PROFILE = 'data:image/svg+xml,' + encodeURIComponent(`
<svg width="200" height="200" xmlns="http://www.w3.org/2000/svg">
  <rect width="200" height="200" fill="#1a1a1a"/>
  <circle cx="100" cy="80" r="35" fill="#333"/>
  <path d="M 50 150 Q 100 120 150 150 L 150 180 L 50 180 Z" fill="#333"/>
</svg>`);

// Initialize the app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('CineBot app initializing...');
    initializeElements();
    attachEventListeners();
    // Set default background on page load
    if (elements.appContainer) {
        elements.appContainer.style.backgroundImage = "url('/background.png')";
        elements.appContainer.style.backgroundSize = 'cover';
        elements.appContainer.style.backgroundPosition = 'center';
    }
    console.log('CineBot app initialized');
});

function initializeElements() {
    elements = {
        // App container
        appContainer: document.getElementById('appContainer'),
        // Connection elements
        connectBtn: document.getElementById('connectBtn'),
        hangupBtn: document.getElementById('hangupBtn'),
        statusText: document.getElementById('statusText'),
        statusIndicator: document.querySelector('.status-indicator'),
        welcomeScreen: document.getElementById('welcomeScreen'),
        
        // Agent elements
        agentContainer: document.getElementById('agentContainer'),
        videoContainer: document.getElementById('videoContainer'),
        
        // Movie display elements
        movieDisplay: document.getElementById('movieDisplay'),
        movieBackdrop: document.getElementById('movieBackdrop'),
        moviePoster: document.getElementById('moviePoster'),
        movieTitle: document.getElementById('movieTitle'),
        movieTagline: document.getElementById('movieTagline'),
        movieYear: document.getElementById('movieYear'),
        movieRuntime: document.getElementById('movieRuntime'),
        movieRating: document.getElementById('movieRating'),
        movieGenres: document.getElementById('movieGenres'),
        movieOverview: document.getElementById('movieOverview'),
        watchProviders: document.getElementById('watchProviders'),
        providersGrid: document.getElementById('providersGrid'),
        castSection: document.getElementById('castSection'),
        castCarousel: document.getElementById('castCarousel'),
        similarSection: document.getElementById('similarSection'),
        similarCarousel: document.getElementById('similarCarousel'),
        
        // Search and trending
        searchResults: document.getElementById('searchResults'),
        searchTitle: document.getElementById('searchTitle'),
        moviesGrid: document.getElementById('moviesGrid'),
        trendingSection: document.getElementById('trendingSection'),
        trendingCarousel: document.getElementById('trendingCarousel'),
        
        // Person display
        personDisplay: document.getElementById('personDisplay'),
        personPhoto: document.getElementById('personPhoto'),
        personName: document.getElementById('personName'),
        personDepartment: document.getElementById('personDepartment'),
        personBirthday: document.getElementById('personBirthday'),
        personBio: document.getElementById('personBio'),
        filmographyCarousel: document.getElementById('filmographyCarousel'),
        
        // Modal and loading
        trailerModal: document.getElementById('trailerModal'),
        trailerFrame: document.getElementById('trailerFrame'),
        loadingState: document.getElementById('loadingState'),
        
        // Buttons
        watchTrailerBtn: document.getElementById('watchTrailerBtn'),
        closeTrailerBtn: document.getElementById('closeTrailerBtn')
    };
}

function attachEventListeners() {
    // Connection buttons
    elements.connectBtn.addEventListener('click', connect);
    elements.hangupBtn.addEventListener('click', disconnect);
    
    // Quick action buttons
    // Trending button removed - use voice commands instead
    
    // Modal close button
    elements.closeTrailerBtn?.addEventListener('click', () => closeTrailer());
}

// Connection Functions
async function connect() {
    try {
        elements.connectBtn.disabled = true;
        elements.connectBtn.textContent = 'Connecting...';
        updateStatus('Connecting...', 'connecting');
        
        // Check if SignalWire SDK is loaded
        if (window.SignalWire && typeof window.SignalWire.SignalWire === 'function') {
            console.log('SignalWire SDK loaded correctly');
        } else {
            console.error('SignalWire SDK structure:', window.SignalWire);
            throw new Error('SignalWire.SignalWire function not found');
        }
        
        console.log('Initializing SignalWire client...');
        
        // Initialize SignalWire client
        client = await window.SignalWire.SignalWire({
            token: STATIC_TOKEN,
            logLevel: 'debug'
        });
        
        console.log('Client initialized, subscribing to events...');
        
        // Subscribe to client events
        client.on('user_event', (params) => {
            console.log('User event from client:', params);
            handleUserEvent(params);
        });
        
        console.log('Dialing to agent...');
        
        // Get video container for remote video
        const videoContainer = document.getElementById('videoContainer');
        
        // Connect to the agent
        roomSession = await client.dial({
            to: DESTINATION,
            rootElement: videoContainer,
            audio: true,
            video: true,
            negotiateVideo: true,
            userVariables: {
                userName: 'CineBot User',
                interface: 'web-ui',
                timestamp: new Date().toISOString(),
                extension: 'cinebot'
            }
        });
        
        console.log('Room session created:', roomSession);
        
        // Subscribe to room session events - match Holy Guacamole exactly
        roomSession.on('call.joined', async (params) => {
            console.log('Call joined:', params);
            handleConnected();
        });
        
        roomSession.on('call.state', (params) => {
            console.log('Call state:', params);
            if (params && params.state === 'active') {
                handleConnected();
            }
        });
        
        roomSession.on('user_event', (params) => {
            console.log('User event from room:', params);
            handleUserEvent(params);
        });
        
        roomSession.on('room.started', (params) => {
            console.log('Room started:', params);
        });
        
        roomSession.on('destroy', (params) => {
            console.log('Room session destroyed:', params);
            handleDisconnect();
        });
        
        roomSession.on('disconnected', (params) => {
            console.log('Disconnected:', params);
            handleDisconnect();
        });
        
        roomSession.on('room.left', (params) => {
            console.log('Room left:', params);
            handleDisconnect();
        });
        
        roomSession.on('call.ended', (params) => {
            console.log('Call ended:', params);
            handleDisconnect();
        });
        
        // Start the call - THIS IS CRITICAL!
        await roomSession.start();
        console.log('Call started');
        
    } catch (error) {
        console.error('Failed to connect:', error);
        console.error('Error details:', error.message, error.stack);
        
        // Handle specific permission errors
        let errorMessage = 'Connection Failed';
        if (error.name === 'NotAllowedError' || error.message.includes('Permission denied')) {
            errorMessage = 'Microphone/Camera access denied. Please allow permissions and try again.';
        } else if (error.name === 'NotFoundError' || error.message.includes('not found')) {
            errorMessage = 'No microphone/camera found. Please check your devices.';
        } else if (error.message) {
            errorMessage = `Connection Failed: ${error.message}`;
        }
        
        updateStatus(errorMessage, 'error');
        elements.connectBtn.disabled = false;
        // Restore button with icon on error
        elements.connectBtn.innerHTML = '';
        const playIcon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        playIcon.setAttribute('viewBox', '0 0 24 24');
        playIcon.setAttribute('width', '18');
        playIcon.setAttribute('height', '18');
        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('d', 'M8 5v14l11-7z');
        path.setAttribute('fill', 'currentColor');
        playIcon.appendChild(path);
        elements.connectBtn.appendChild(playIcon);
        const span = document.createElement('span');
        span.textContent = 'Connect to CineBot';
        elements.connectBtn.appendChild(span);
        
        // Reset state
        client = null;
        roomSession = null;
    }
}

async function disconnect() {
    console.log('Disconnecting...');
    
    try {
        if (roomSession) {
            await roomSession.hangup();
            roomSession = null;
        }
        
        if (client) {
            await client.disconnect();
            client = null;
        }
    } catch (error) {
        console.error('Error during disconnect:', error);
    }
    
    handleDisconnect();
}

function handleConnected() {
    console.log('Connected successfully');
    updateStatus('Connected', 'connected');
    
    // Hide welcome screen
    if (elements.welcomeScreen) {
        elements.welcomeScreen.style.display = 'none';
    }
    
    // Ensure agent container and video are visible
    if (elements.agentContainer) {
        elements.agentContainer.style.display = 'block';
        elements.agentContainer.style.visibility = 'visible';
    }
    if (elements.videoContainer) {
        elements.videoContainer.style.display = 'block';
        elements.videoContainer.style.visibility = 'visible';
    }
    
    // Update buttons
    elements.connectBtn.style.display = 'none';
    elements.hangupBtn.style.display = 'flex';
    
    // Quick actions removed
    
    // Show voice indicator
    // Voice indicator removed
}

function handleDisconnect() {
    console.log('Disconnected');
    
    // Prevent multiple disconnect calls
    if (!roomSession && !client) {
        return;
    }
    
    // Hide status indicator when disconnected
    document.getElementById('connectionStatus').style.display = 'none';
    
    // Clear any displayed content
    clearAllDisplays();
    
    // Force move agent back to center on disconnect
    moveAgentToCenter(true);
    
    // Show welcome screen
    if (elements.welcomeScreen) {
        elements.welcomeScreen.style.display = 'flex';
    }
    
    // Update buttons and restore connect button with icon
    elements.connectBtn.style.display = 'flex';
    elements.connectBtn.disabled = false;
    // Clear and rebuild connect button
    elements.connectBtn.innerHTML = '';
    const playIcon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    playIcon.setAttribute('viewBox', '0 0 24 24');
    playIcon.setAttribute('width', '18');
    playIcon.setAttribute('height', '18');
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', 'M8 5v14l11-7z');
    path.setAttribute('fill', 'currentColor');
    playIcon.appendChild(path);
    elements.connectBtn.appendChild(playIcon);
    const span = document.createElement('span');
    span.textContent = 'Connect to CineBot';
    elements.connectBtn.appendChild(span);
    elements.hangupBtn.style.display = 'none';
    
    // Quick actions removed
    
    // Hide voice indicator
    // Voice indicator removed
    
    // Reset state
    roomSession = null;
    client = null;
    isContentDisplayed = false; // Reset the flag
}

// Event Handler
function handleUserEvent(params) {
    console.log('Handling user event:', params);
    
    // Extract event data - handle different event structures
    let eventData = params;
    if (params && params.params) {
        eventData = params.params;
    }
    if (params && params.event) {
        eventData = params.event;
    }
    
    if (!eventData || !eventData.type) {
        console.log('No valid event data found');
        return;
    }
    
    switch (eventData.type) {
        case 'movie_search_results':
            console.log('Received movie_search_results event:', eventData.data);
            displaySearchResults(eventData.data);
            break;
        case 'movie_details':
            displayMovieDetails(eventData.data);
            break;
        case 'cast_crew_display':
            displayCastCrew(eventData.data);
            break;
        case 'trailer_available':
            // Automatically play the trailer when AI sends it
            if (eventData.data.video) {
                playTrailer(eventData.data.video);
            }
            break;
        case 'person_details':
            displayPersonDetails(eventData.data);
            break;
        case 'person_search_results':
            displayPersonSearchResults(eventData.data);
            break;
        case 'trending_movies':
            displayTrending(eventData.data);
            break;
        case 'similar_movies':
            displaySimilarMovies(eventData.data);
            break;
        case 'similar_movie':
            displaySimilarMovies(eventData.data);
            break;
        case 'genre_movies':
            displayGenreMovies(eventData.data);
            break;
        case 'watch_providers':
            displayWatchProviders(eventData.data);
            break;
        case 'clear_display':
            clearAllDisplays();
            break;
        case 'tv_details':
            displayTVDetails(eventData.data);
            break;
        case 'tv_search_results':
            displayTVSearchResults(eventData.data);
            break;
        case 'season_details':
            displaySeasonDetails(eventData.data);
            break;
        case 'trending_tv':
            displayTrendingTV(eventData.data);
            break;
        case 'multi_search_results':
            displayMultiSearchResults(eventData.data);
            break;
        case 'now_playing':
            displayNowPlaying(eventData.data);
            break;
        case 'video_available':
            if (eventData.data.video) {
                playTrailer(eventData.data.video);
            }
            break;
        case 'videos_available':
            if (eventData.data.playing) {
                playTrailer(eventData.data.playing);
            }
            break;
        case 'watchlist_updated':
            console.log('Watchlist updated:', eventData.data.watchlist);
            // Could display a notification or update UI
            break;
        case 'discover_movie_results':
            displayDiscoverResults(eventData.data, 'movie');
            break;
        case 'discover_tv_results':
            displayDiscoverResults(eventData.data, 'tv');
            break;
        case 'similar_tv':
            displaySimilarTV(eventData.data);
            break;
        case 'person_search_results':
            displayPersonSearchResults(eventData.data);
            break;
        case 'genre_movies':
            displayGenreMovies(eventData.data);
            break;
    }
}

// Display Functions
function displaySearchResults(data) {
    clearAllDisplays();
    hideAllSections();
    elements.searchResults.classList.remove('hidden');
    elements.searchTitle.textContent = 'Search Results';
    elements.moviesGrid.innerHTML = '';
    
    data.results.forEach((movie, index) => {
        const card = createMovieCard(movie, index + 1);
        elements.moviesGrid.appendChild(card);
    });
    
    moveAgentToCorner();
    // Audio handled by backend
}

function displayMovieDetails(details) {
    clearAllDisplays();
    hideAllSections();
    
    // Clear the default background when showing movie content
    if (elements.appContainer) {
        elements.appContainer.style.backgroundImage = 'none';
    }
    
    // Move agent to corner when displaying content
    if (!isContentDisplayed) {
        moveAgentToCorner();
        isContentDisplayed = true;
    }
    
    // Set the entire page background to the movie's backdrop
    if (details.backdrop_path) {
        document.body.style.backgroundImage = `linear-gradient(to bottom, rgba(0,0,0,0.4), rgba(0,0,0,0.8)), url(${details.backdrop_path})`;
        document.body.style.backgroundSize = 'cover';
        document.body.style.backgroundPosition = 'center';
        document.body.style.backgroundAttachment = 'fixed';
    }
    
    // Set backdrop and poster
    if (details.backdrop_path) {
        elements.movieBackdrop.src = details.backdrop_path;
        elements.movieBackdrop.style.display = 'block';
    } else {
        elements.movieBackdrop.style.display = 'none';
    }
    
    if (details.poster_path) {
        elements.moviePoster.src = details.poster_path;
    } else {
        elements.moviePoster.src = ''; // Let CSS placeholder show
    }
    
    // Set movie info
    elements.movieTitle.textContent = details.title;
    elements.movieTagline.textContent = details.tagline || '';
    
    // Add content rating badge before year/runtime
    const metaContainer = document.querySelector('.movie-meta');
    metaContainer.innerHTML = ''; // Clear existing content
    
    // Add content rating badge if available
    if (details.content_rating) {
        const ratingBadge = document.createElement('span');
        ratingBadge.className = `content-rating rating-${details.content_rating.toLowerCase().replace('-', '')}`;
        ratingBadge.textContent = details.content_rating;
        metaContainer.appendChild(ratingBadge);
    }
    
    // Add year
    if (details.release_date) {
        const yearSpan = document.createElement('span');
        yearSpan.className = 'movie-year';
        yearSpan.textContent = details.release_date.split('-')[0];
        metaContainer.appendChild(yearSpan);
    }
    
    // Add runtime
    if (details.runtime) {
        const runtimeSpan = document.createElement('span');
        runtimeSpan.className = 'movie-runtime';
        runtimeSpan.textContent = `${details.runtime} min`;
        metaContainer.appendChild(runtimeSpan);
    }
    
    // Create star rating display
    const rating = details.vote_average || 0;
    const stars = Math.round(rating / 2); // Convert 10-point scale to 5 stars
    const starDisplay = '★'.repeat(stars) + '☆'.repeat(5 - stars);
    
    const ratingSpan = document.createElement('span');
    ratingSpan.className = 'movie-rating';
    ratingSpan.innerHTML = `
        <svg class="star-icon" viewBox="0 0 24 24">
            <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
        </svg>
        ${starDisplay} <span class="rating-number">${rating.toFixed(1)}/10</span>
    `;
    metaContainer.appendChild(ratingSpan);
    
    elements.movieOverview.textContent = details.overview || '';
    
    // Set genres
    elements.movieGenres.innerHTML = '';
    if (details.genres) {
        details.genres.forEach(genre => {
            const tag = document.createElement('span');
            tag.className = 'genre-tag';
            tag.textContent = genre;
            elements.movieGenres.appendChild(tag);
        });
    }
    
    // Display streaming providers if available
    if (details.watch_providers && details.watch_providers.providers) {
        displayWatchProviders(details.watch_providers);
    }
    
    // Show cast if available
    if (details.cast && details.cast.length > 0) {
        displayCastCrew({ cast: details.cast, crew: details.crew || [] });
    }
    
    // Don't show similar movies since we can't interact with them
    
    elements.movieDisplay.classList.remove('hidden');
    moveAgentToCorner();
    // Audio handled by backend
}

function displayCastCrew(data) {
    // Note: This only updates the cast section, not the full display
    // If this is being called without movie_details, we should not clear the display
    elements.castCarousel.innerHTML = '';
    
    if (data.cast && data.cast.length > 0) {
        data.cast.forEach(member => {
            const card = document.createElement('div');
            card.className = 'cast-member';
            card.innerHTML = `
                <img src="${member.profile_path || PLACEHOLDER_PROFILE}" alt="${member.name}" class="cast-photo" onerror="this.src='${PLACEHOLDER_PROFILE}'">
                <div class="cast-name">${member.name}</div>
                <div class="cast-character">${member.character || ''}</div>
            `;
            // No click handler - browser can't send events to AI
            elements.castCarousel.appendChild(card);
        });
        
        elements.castSection.classList.remove('hidden');
    }
}

function displaySimilarMovies(data) {
    // Clear everything and hide default background
    clearAllDisplays();
    hideAllSections();
    
    // Clear the default background
    if (elements.appContainer) {
        elements.appContainer.style.backgroundImage = 'none';
    }
    
    // Move agent to corner
    if (!isContentDisplayed) {
        moveAgentToCorner();
        isContentDisplayed = true;
    }
    
    // Show similar movies in the search results section
    elements.searchResults.classList.remove('hidden');
    elements.searchTitle.textContent = 'Similar Movies';
    elements.moviesGrid.innerHTML = '';
    
    // Handle both data.movies and data.items formats
    const movies = data.movies || data.items || [];
    
    if (movies.length > 0) {
        movies.forEach((movie, index) => {
            const card = createMovieCard(movie, index + 1);
            elements.moviesGrid.appendChild(card);
        });
    }
}

function displayNowPlaying(data) {
    // Clear everything first
    clearAllDisplays();
    
    // Clear the default background when showing now playing content
    if (elements.appContainer) {
        elements.appContainer.style.backgroundImage = 'none';
    }
    
    // Then display now playing movies
    hideAllSections();
    elements.searchResults.classList.remove('hidden');
    elements.searchTitle.textContent = 'Now Playing in Theaters';
    elements.moviesGrid.innerHTML = '';
    elements.moviesGrid.className = 'movies-grid'; // Reset class name
    
    // Display dates if available
    if (data.dates) {
        const dateInfo = document.createElement('div');
        dateInfo.className = 'date-info';
        dateInfo.style.cssText = 'text-align: center; margin-bottom: 20px; color: rgba(255,255,255,0.7); font-size: 0.9rem;';
        dateInfo.textContent = `Showing movies from ${new Date(data.dates.minimum).toLocaleDateString()} to ${new Date(data.dates.maximum).toLocaleDateString()}`;
        elements.searchResults.insertBefore(dateInfo, elements.moviesGrid);
    }
    
    // Display all now playing movies in a grid with position numbers
    if (data && data.results) {
        data.results.forEach((movie, index) => {
            const card = createMovieCard(movie, index + 1);
            
            // Add "In Theaters" badge
            const badge = document.createElement('div');
            badge.className = 'in-theaters-badge';
            badge.style.cssText = 'position: absolute; bottom: 10px; left: 10px; background: rgba(229, 9, 20, 0.9); color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.75rem; text-transform: uppercase; z-index: 1;';
            badge.textContent = 'IN THEATERS';
            card.style.position = 'relative';
            card.appendChild(badge);
            
            elements.moviesGrid.appendChild(card);
        });
    }
    
    // Move agent to corner when displaying content
    if (!isContentDisplayed) {
        moveAgentToCorner();
        isContentDisplayed = true;
    }
}

function displayTrending(data) {
    // Clear everything first
    clearAllDisplays();
    
    // Clear the default background when showing trending content
    if (elements.appContainer) {
        elements.appContainer.style.backgroundImage = 'none';
    }
    
    // Then display trending
    hideAllSections();
    elements.searchResults.classList.remove('hidden');
    elements.searchTitle.textContent = 'Trending Movies This Week';
    elements.moviesGrid.innerHTML = '';
    elements.moviesGrid.className = 'movies-grid'; // Reset class name
    
    // Display all trending movies in a grid with position numbers
    if (data && data.results) {
        data.results.forEach((movie, index) => {
            const card = createMovieCard(movie, index + 1);
            elements.moviesGrid.appendChild(card);
        });
    }
    
    // Move agent to corner when displaying content
    if (!isContentDisplayed) {
        moveAgentToCorner();
        isContentDisplayed = true;
    }
}

// TV Show Display Functions
function displayTVDetails(details) {
    clearAllDisplays();
    hideAllSections();
    
    // Clear the default background when showing TV content
    if (elements.appContainer) {
        elements.appContainer.style.backgroundImage = 'none';
    }
    
    // Move agent to corner when displaying content
    if (!isContentDisplayed) {
        moveAgentToCorner();
        isContentDisplayed = true;
    }
    
    // Set the entire page background to the TV show's backdrop
    if (details.backdrop_path) {
        document.body.style.backgroundImage = `linear-gradient(to bottom, rgba(0,0,0,0.4), rgba(0,0,0,0.8)), url(${details.backdrop_path})`;
        document.body.style.backgroundSize = 'cover';
        document.body.style.backgroundPosition = 'center';
        document.body.style.backgroundAttachment = 'fixed';
    }
    
    // Set backdrop and poster
    if (details.backdrop_path) {
        elements.movieBackdrop.src = details.backdrop_path;
        elements.movieBackdrop.style.display = 'block';
    } else {
        elements.movieBackdrop.style.display = 'none';
    }
    
    if (details.poster_path) {
        elements.moviePoster.src = details.poster_path;
    }
    
    // Set TV show info (reusing movie elements since layout is similar)
    elements.movieTitle.textContent = details.name || '';
    elements.movieTagline.textContent = details.tagline || '';
    
    // Format TV-specific metadata
    const firstAirYear = details.first_air_date ? new Date(details.first_air_date).getFullYear() : '';
    const lastAirYear = details.last_air_date ? new Date(details.last_air_date).getFullYear() : '';
    const yearRange = lastAirYear && lastAirYear !== firstAirYear ? `${firstAirYear}-${lastAirYear}` : firstAirYear;
    elements.movieYear.textContent = yearRange;
    
    // Show comprehensive TV show runtime and season info
    let runtimeText = [];
    
    // Add episode runtime if available
    if (details.episode_run_time && Array.isArray(details.episode_run_time) && details.episode_run_time.length > 0) {
        const avgRuntime = Math.round(details.episode_run_time.reduce((a, b) => a + b, 0) / details.episode_run_time.length);
        runtimeText.push(`${avgRuntime} min/episode`);
    }
    
    // Add season count
    if (details.number_of_seasons) {
        runtimeText.push(`${details.number_of_seasons} season${details.number_of_seasons !== 1 ? 's' : ''}`);
    }
    
    // Add episode count
    if (details.number_of_episodes) {
        runtimeText.push(`${details.number_of_episodes} episodes`);
    }
    
    // Set the runtime text or show status if no runtime info
    if (runtimeText.length > 0) {
        elements.movieRuntime.textContent = runtimeText.join(' • ');
    } else if (details.status) {
        elements.movieRuntime.textContent = details.status;
    } else {
        elements.movieRuntime.textContent = '';
    }
    
    elements.movieRating.textContent = details.vote_average ? details.vote_average.toFixed(1) : 'N/A';
    
    // Set genres
    elements.movieGenres.innerHTML = '';
    if (details.genres) {
        details.genres.forEach(genre => {
            const genreTag = document.createElement('span');
            genreTag.className = 'genre-tag';
            genreTag.textContent = genre;
            elements.movieGenres.appendChild(genreTag);
        });
    }
    
    elements.movieOverview.textContent = details.overview || '';
    
    // Display cast if available
    if (details.cast && details.cast.length > 0) {
        elements.castCarousel.innerHTML = '';
        details.cast.slice(0, 10).forEach(member => {
            const card = document.createElement('div');
            card.className = 'cast-member';
            card.innerHTML = `
                <img src="${member.profile_path || PLACEHOLDER_PROFILE}" alt="${member.name}" class="cast-photo" onerror="this.src='${PLACEHOLDER_PROFILE}'">
                <div class="cast-name">${member.name}</div>
                <div class="cast-character">${member.character || ''}</div>
            `;
            elements.castCarousel.appendChild(card);
        });
        elements.castSection.classList.remove('hidden');
    }
    
    // Display seasons if available (TV shows have seasons data)
    if (details.seasons && details.seasons.length > 0) {
        console.log(`Displaying ${details.seasons.length} seasons for TV show`);
        
        // Create or find seasons section
        let seasonsSection = document.getElementById('seasonsSection');
        if (!seasonsSection) {
            seasonsSection = document.createElement('div');
            seasonsSection.id = 'seasonsSection';
            seasonsSection.className = 'seasons-section';
            seasonsSection.innerHTML = '<h2>Seasons</h2><div class="seasons-carousel" id="seasonsCarousel"></div>';
            // Insert after cast section or at end of movie content
            const movieContent = document.querySelector('.movie-content');
            if (movieContent) {
                movieContent.appendChild(seasonsSection);
            }
        }
        
        const seasonsCarousel = document.getElementById('seasonsCarousel');
        seasonsCarousel.innerHTML = '';
        
        // Sort seasons by season number and display all
        const sortedSeasons = [...details.seasons].sort((a, b) => a.season_number - b.season_number);
        
        sortedSeasons.forEach((season, index) => {
            // Only skip season 0 if it has no episodes
            if (season.season_number === 0 && season.episode_count === 0) return;
            
            const seasonCard = document.createElement('div');
            seasonCard.className = 'season-card';
            
            // Handle special season 0
            const seasonLabel = season.season_number === 0 ? 'Specials' : `Season ${season.season_number}`;
            
            seasonCard.innerHTML = `
                <div class="season-number">${seasonLabel}</div>
                <div class="season-name">${season.name || seasonLabel}</div>
                <div class="season-episodes">${season.episode_count || 0} episodes</div>
                ${season.air_date ? `<div class="season-year">${new Date(season.air_date).getFullYear()}</div>` : ''}
            `;
            seasonsCarousel.appendChild(seasonCard);
        });
        
        seasonsSection.classList.remove('hidden');
        seasonsSection.style.display = 'block'; // Force display
    } else {
        console.log('No seasons data available for TV show');
    }
    
    // Don't display similar shows by default for TV - only show if explicitly requested
    // Hide the similar section for TV shows
    if (elements.similarSection) {
        elements.similarSection.classList.add('hidden');
    }
    
    // Display watch providers if available
    if (details.watch_providers && details.watch_providers.providers) {
        displayWatchProviders(details.watch_providers);
    }
    
    // Store current trailer if available
    if (details.videos && details.videos.length > 0) {
        currentTrailer = details.videos[0];
    }
    
    elements.movieDisplay.classList.remove('hidden');
    moveAgentToCorner();
}

function displayTVSearchResults(data) {
    clearAllDisplays();
    hideAllSections();
    elements.searchResults.classList.remove('hidden');
    elements.searchTitle.textContent = 'TV Show Search Results';
    elements.moviesGrid.innerHTML = '';
    
    data.results.forEach((show, index) => {
        const card = createTVCard(show, index + 1);
        elements.moviesGrid.appendChild(card);
    });
    
    moveAgentToCorner();
}

function displayTrendingTV(data) {
    clearAllDisplays();
    
    // Clear the default background when showing trending TV content
    if (elements.appContainer) {
        elements.appContainer.style.backgroundImage = 'none';
    }
    
    hideAllSections();
    elements.searchResults.classList.remove('hidden');
    elements.searchTitle.textContent = 'Trending TV Shows This Week';
    elements.moviesGrid.innerHTML = '';
    elements.moviesGrid.className = 'movies-grid'; // Reset class name
    
    // Display all trending TV shows in a grid with position numbers
    if (data && data.results) {
        data.results.forEach((show, index) => {
            const card = createTVCard(show, index + 1);
            elements.moviesGrid.appendChild(card);
        });
    }
    
    // Move agent to corner when displaying content
    if (!isContentDisplayed) {
        moveAgentToCorner();
        isContentDisplayed = true;
    }
}

function displaySeasonDetails(data) {
    clearAllDisplays();
    hideAllSections();
    
    // Clear the default background when showing season content
    if (elements.appContainer) {
        elements.appContainer.style.backgroundImage = 'none';
    }
    
    // Move agent to corner when displaying content
    if (!isContentDisplayed) {
        moveAgentToCorner();
        isContentDisplayed = true;
    }
    
    // Display season details as a list of episodes
    elements.searchResults.classList.remove('hidden');
    elements.searchTitle.textContent = `${data.name || 'Season Details'}`;
    elements.moviesGrid.innerHTML = '';
    elements.moviesGrid.className = 'episode-list'; // Use different styling for episodes
    
    if (data.episodes && Array.isArray(data.episodes)) {
        data.episodes.forEach((episode, index) => {
            const episodeCard = document.createElement('div');
            episodeCard.className = 'episode-card';
            episodeCard.style.position = 'relative';
            
            // Add episode number badge
            const badge = document.createElement('div');
            badge.style.cssText = 'position: absolute; top: 10px; left: 10px; background: rgba(229, 9, 20, 0.9); color: white; padding: 6px 10px; border-radius: 16px; font-size: 0.9rem; font-weight: bold; z-index: 1;';
            badge.textContent = `E${episode.episode_number || index + 1}`;
            episodeCard.appendChild(badge);
            
            // Episode thumbnail
            if (episode.still_path) {
                const thumbnail = document.createElement('img');
                thumbnail.src = episode.still_path;
                thumbnail.alt = episode.name || `Episode ${episode.episode_number}`;
                thumbnail.className = 'episode-thumbnail';
                thumbnail.onerror = function() { this.src = PLACEHOLDER_POSTER; };
                episodeCard.appendChild(thumbnail);
            }
            
            // Episode info
            const info = document.createElement('div');
            info.className = 'episode-info';
            
            const title = document.createElement('h3');
            title.className = 'episode-title';
            title.textContent = `${episode.episode_number}. ${episode.name || `Episode ${episode.episode_number}`}`;
            info.appendChild(title);
            
            if (episode.air_date) {
                const airDate = document.createElement('div');
                airDate.className = 'episode-air-date';
                airDate.textContent = `Aired: ${new Date(episode.air_date).toLocaleDateString()}`;
                info.appendChild(airDate);
            }
            
            if (episode.runtime) {
                const runtime = document.createElement('div');
                runtime.className = 'episode-runtime';
                runtime.textContent = `${episode.runtime} minutes`;
                info.appendChild(runtime);
            }
            
            if (episode.overview) {
                const overview = document.createElement('p');
                overview.className = 'episode-overview';
                overview.textContent = episode.overview;
                info.appendChild(overview);
            }
            
            if (episode.vote_average) {
                const rating = document.createElement('div');
                rating.className = 'episode-rating';
                rating.innerHTML = `⭐ ${episode.vote_average.toFixed(1)}/10`;
                info.appendChild(rating);
            }
            
            episodeCard.appendChild(info);
            elements.moviesGrid.appendChild(episodeCard);
        });
    } else {
        // Fallback if no episodes data
        const noData = document.createElement('div');
        noData.className = 'no-data-message';
        noData.textContent = 'No episode information available';
        elements.moviesGrid.appendChild(noData);
    }
    
    moveAgentToCorner();
}

function createTVCard(show, position = null) {
    const card = document.createElement('div');
    card.className = 'movie-card';
    card.style.position = 'relative';
    
    const firstAirYear = show.first_air_date ? ` (${new Date(show.first_air_date).getFullYear()})` : '';
    
    // Add position number badge if provided
    const positionBadge = position ? `
        <div style="position: absolute; top: 10px; right: 10px; background: rgba(229, 9, 20, 0.9); color: white; padding: 6px; border-radius: 50%; font-size: 1rem; font-weight: bold; z-index: 1; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;">
            ${position}
        </div>` : '';
    
    card.innerHTML = `
        ${positionBadge}
        <img src="${show.poster_path || PLACEHOLDER_POSTER}" alt="${show.name}" class="movie-card-poster" onerror="this.src='${PLACEHOLDER_POSTER}'">
        <div class="movie-card-title">
            ${show.name}
            <div class="movie-card-year">${firstAirYear}</div>
        </div>
    `;
    
    // Store ID as data attribute for debugging
    card.dataset.tvId = show.id;
    
    return card;
}

function createPersonCard(person, position = null) {
    const card = document.createElement('div');
    card.className = 'movie-card';
    card.style.position = 'relative';
    
    const knownFor = person.known_for_department || 'Unknown';
    const knownForMovies = person.known_for && person.known_for.length > 0 
        ? person.known_for.map(item => item.title || item.name).slice(0, 2).join(', ')
        : '';
    
    // Add position number badge if provided
    const positionBadge = position ? `
        <div style="position: absolute; top: 10px; right: 10px; background: rgba(229, 9, 20, 0.9); color: white; padding: 6px; border-radius: 50%; font-size: 1rem; font-weight: bold; z-index: 1; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;">
            ${position}
        </div>` : '';
    
    card.innerHTML = `
        ${positionBadge}
        <img src="${person.profile_path ? `https://image.tmdb.org/t/p/w500${person.profile_path}` : PLACEHOLDER_PROFILE}" alt="${person.name}" class="movie-card-poster" onerror="this.src='${PLACEHOLDER_PROFILE}'">
        <div class="movie-card-title">
            ${person.name}
            <div class="movie-card-year">${knownFor}</div>
            ${knownForMovies ? `<div style="font-size: 0.8em; color: #999; margin-top: 4px;">${knownForMovies}</div>` : ''}
        </div>
    `;
    
    // Store ID as data attribute for debugging
    card.dataset.personId = person.id;
    
    return card;
}

function displayMultiSearchResults(data) {
    clearAllDisplays();
    hideAllSections();
    
    // Clear the default background
    if (elements.appContainer) {
        elements.appContainer.style.backgroundImage = 'none';
    }
    
    // Move agent to corner
    if (!isContentDisplayed) {
        moveAgentToCorner();
        isContentDisplayed = true;
    }
    
    elements.searchResults.classList.remove('hidden');
    elements.searchTitle.textContent = 'Search Results (Movies & TV Shows)';
    elements.moviesGrid.innerHTML = '';
    
    if (data.results) {
        data.results.forEach((item, index) => {
            let card;
            const position = index + 1; // Add position for numbering
            if (item.media_type === 'tv') {
                card = createTVCard(item, position);
            } else if (item.media_type === 'movie') {
                card = createMovieCard(item, position);
            } else if (item.media_type === 'person') {
                // Could create a person card in future
                return;
            }
            if (card) {
                // Add a media type badge
                const badge = document.createElement('div');
                badge.className = 'media-type-badge';
                badge.textContent = item.media_type === 'tv' ? 'TV' : 'Movie';
                badge.style.cssText = 'position: absolute; top: 10px; left: 10px; background: rgba(0,0,0,0.8); color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.75rem; text-transform: uppercase; z-index: 1;';
                card.style.position = 'relative';
                card.appendChild(badge);
                elements.moviesGrid.appendChild(card);
            }
        });
    }
}

function displayPersonDetails(person) {
    clearAllDisplays();
    hideAllSections();
    
    // Use the search results section to display person with all their movies
    elements.searchResults.classList.remove('hidden');
    
    // Create a header section for person info
    const headerHTML = `
        <div style="display: flex; gap: 30px; margin-bottom: 40px; padding: 20px; background: rgba(0,0,0,0.5); border-radius: 12px;">
            <img src="${person.profile_path || PLACEHOLDER_PROFILE}" 
                 style="width: 200px; height: 300px; object-fit: cover; border-radius: 8px;"
                 onerror="this.src='${PLACEHOLDER_PROFILE}'">
            <div style="flex: 1;">
                <h2 style="font-size: 2rem; margin-bottom: 10px;">${person.name}</h2>
                <p style="color: var(--accent); margin-bottom: 10px; font-size: 0.95rem;">${person.known_for_department || ''}</p>
                ${person.birthday ? `<p style="margin-bottom: 10px; font-size: 0.9rem;">Born: ${person.birthday}${person.deathday ? ` - Died: ${person.deathday}` : ''}</p>` : ''}
                ${person.total_movie_count ? `<p style="margin-bottom: 15px; font-size: 0.9rem;">Total Movies: ${person.total_movie_count}</p>` : ''}
                <p style="line-height: 1.5; max-height: 200px; overflow-y: auto; font-size: 0.85rem; color: rgba(255,255,255,0.8);">${person.biography || 'No biography available.'}</p>
            </div>
        </div>
    `;
    
    elements.searchTitle.innerHTML = headerHTML;
    
    // Display all movies in a grid
    elements.moviesGrid.innerHTML = '';
    if (person.filmography && person.filmography.length > 0) {
        person.filmography.forEach(movie => {
            const card = createMovieCard(movie);
            elements.moviesGrid.appendChild(card);
        });
    }
    
    moveAgentToCorner();
}

function displayPersonSearchResults(data) {
    clearAllDisplays();
    hideAllSections();
    elements.searchResults.classList.remove('hidden');
    elements.searchTitle.textContent = 'People Search Results';
    elements.moviesGrid.innerHTML = '';
    
    data.results.forEach(person => {
        const card = document.createElement('div');
        card.className = 'person-card movie-card';
        card.innerHTML = `
            <img src="${person.profile_path || '/assets/no-profile.jpg'}" alt="${person.name}" class="movie-card-poster">
            <div class="movie-card-title">${person.name}</div>
        `;
        // No click handler - browser can't send events to AI
        elements.moviesGrid.appendChild(card);
    });
    
    moveAgentToCorner();
}

function displayGenreMovies(data) {
    clearAllDisplays();
    hideAllSections();
    elements.searchResults.classList.remove('hidden');
    elements.searchTitle.textContent = `${data.genre} Movies`;
    elements.moviesGrid.innerHTML = '';
    
    data.movies.forEach(movie => {
        const card = createMovieCard(movie);
        elements.moviesGrid.appendChild(card);
    });
    
    moveAgentToCorner();
}

function displayWatchProviders(data) {
    if (!data.providers || data.providers.length === 0) return;
    
    elements.providersGrid.innerHTML = '';
    
    // Add small heading if we have a link
    if (data.link) {
        const heading = document.createElement('span');
        heading.className = 'providers-heading';
        heading.textContent = 'Watch: ';
        elements.providersGrid.appendChild(heading);
    }
    
    data.providers.forEach(provider => {
        const providerLink = document.createElement('a');
        providerLink.className = 'provider-logo';
        providerLink.href = data.link || '#';
        providerLink.target = '_blank'; // Opens in new tab
        providerLink.rel = 'noopener noreferrer'; // Security best practice
        providerLink.title = `Watch on ${provider.provider_name}`;
        providerLink.innerHTML = `
            <img src="${provider.logo_path}" alt="${provider.provider_name}">
            <span class="provider-type">${provider.type === 'flatrate' ? 'Stream' : provider.type === 'rent' ? 'Rent' : provider.type === 'buy' ? 'Buy' : 'Free'}</span>
        `;
        elements.providersGrid.appendChild(providerLink);
    });
    
    elements.watchProviders.classList.remove('hidden');
}

// Helper Functions
function createMovieCard(movie, position = null) {
    const card = document.createElement('div');
    card.className = 'movie-card';
    card.style.position = 'relative';
    
    // Add position number badge if provided
    if (position) {
        const badge = document.createElement('div');
        badge.style.cssText = 'position: absolute; top: 10px; right: 10px; background: rgba(229, 9, 20, 0.9); color: white; padding: 6px; border-radius: 50%; font-size: 1rem; font-weight: bold; z-index: 1; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;';
        badge.textContent = position;
        card.appendChild(badge);
    }
    
    const poster = document.createElement('img');
    poster.src = movie.poster_path || PLACEHOLDER_POSTER;
    poster.alt = movie.title;
    poster.className = 'movie-card-poster';
    poster.onerror = function() { this.src = PLACEHOLDER_POSTER; };
    
    const title = document.createElement('div');
    title.className = 'movie-card-title';
    title.textContent = movie.title;
    
    // Add year if available for better identification
    if (movie.release_date) {
        const year = document.createElement('div');
        year.className = 'movie-card-year';
        year.textContent = movie.release_date.substring(0, 4);
        title.appendChild(year);
    }
    
    card.appendChild(poster);
    card.appendChild(title);
    
    // Store ID as data attribute for debugging
    card.dataset.movieId = movie.id;
    
    // No click handler - browser can't send events to AI
    
    return card;
}

function moveAgentToCorner() {
    if (elements.agentContainer) {
        elements.agentContainer.classList.remove('centered');
        elements.agentContainer.classList.add('corner');
        // Ensure the container is visible
        elements.agentContainer.style.display = 'block';
        elements.agentContainer.style.visibility = 'visible';
        isContentDisplayed = true; // Once moved to corner, stay there
    }
}

function moveAgentToCenter(forceMove = false) {
    // Only move to center if we haven't displayed content yet
    // or if explicitly forced (during disconnect)
    if (elements.agentContainer && (!isContentDisplayed || forceMove)) {
        elements.agentContainer.classList.remove('corner');
        elements.agentContainer.classList.add('centered');
        // Ensure the container is visible
        elements.agentContainer.style.display = 'block';
        elements.agentContainer.style.visibility = 'visible';
        if (forceMove) {
            isContentDisplayed = false; // Reset the flag if forced
        }
    }
}

function hideAllSections() {
    // Hide content sections but NEVER hide the agent container
    elements.movieDisplay.classList.add('hidden');
    elements.searchResults.classList.add('hidden');
    elements.trendingSection.classList.add('hidden');
    elements.personDisplay.classList.add('hidden');
    elements.trailerModal.classList.add('hidden');
    elements.castSection.classList.add('hidden');
    elements.similarSection.classList.add('hidden');
    elements.watchProviders.classList.add('hidden');
    
    // Also reset the background when hiding sections
    document.body.style.backgroundImage = '';
    document.body.style.backgroundSize = '';
    document.body.style.backgroundPosition = '';
    document.body.style.backgroundAttachment = '';
    
    // Ensure agent container stays visible
    if (elements.agentContainer) {
        elements.agentContainer.style.display = 'block';
        elements.agentContainer.style.visibility = 'visible';
    }
}

function clearAllDisplays() {
    hideAllSections();
    // Don't move agent back to center - it should stay in corner once content has been shown
    // Only move back to center on disconnect
    elements.trailerFrame.src = '';
    
    // Clear any dynamically created seasons section
    const seasonsSection = document.getElementById('seasonsSection');
    if (seasonsSection) {
        seasonsSection.remove();
    }
    
    // Reset the background to default background.png
    document.body.style.backgroundImage = '';
    document.body.style.backgroundSize = '';
    document.body.style.backgroundPosition = '';
    document.body.style.backgroundAttachment = '';
    if (elements.appContainer) {
        elements.appContainer.style.backgroundImage = "url('/background.png')";
        elements.appContainer.style.backgroundSize = 'cover';
        elements.appContainer.style.backgroundPosition = 'center';
    }
}

// Trailer Functions
let currentTrailer = null;

function playTrailer(video) {
    const trailerVideo = video || currentTrailer;
    if (trailerVideo) {
        elements.trailerFrame.src = `https://www.youtube.com/embed/${trailerVideo.key}?autoplay=1`;
        elements.trailerModal.classList.remove('hidden');
        currentTrailer = trailerVideo;
    }
}

function enableTrailerButton(video) {
    currentTrailer = video;
    elements.watchTrailerBtn.disabled = false;
}

function closeTrailer() {
    elements.trailerModal.classList.add('hidden');
    elements.trailerFrame.src = '';
}

// Utility Functions
function speakToAgent(message) {
    // In a voice-driven interface, this would trigger voice input
    // For now, we'll just log it
    console.log('Speaking to agent:', message);
}

function updateStatus(text, status) {
    if (elements.statusText) {
        elements.statusText.textContent = text;
    }
    if (elements.statusIndicator) {
        elements.statusIndicator.className = `status-indicator ${status}`;
    }
    // Only show status during connection
    if (status === 'connecting' || status === 'connected' || status === 'error') {
        document.getElementById('connectionStatus').style.display = 'flex';
    } else {
        document.getElementById('connectionStatus').style.display = 'none';
    }
}

function showLoading() {
    elements.loadingState.classList.remove('hidden');
}

function hideLoading() {
    elements.loadingState.classList.add('hidden');
}

// Display function for person search results
function displayPersonSearchResults(data) {
    clearAllDisplays();
    hideAllSections();
    elements.searchResults.classList.remove('hidden');
    elements.searchTitle.textContent = 'People Search Results';
    elements.moviesGrid.innerHTML = '';
    
    data.results.forEach((person, index) => {
        const card = createPersonCard(person, index + 1);
        elements.moviesGrid.appendChild(card);
    });
}

// Display function for genre movies
function displayGenreMovies(data) {
    clearAllDisplays();
    hideAllSections();
    elements.searchResults.classList.remove('hidden');
    elements.searchTitle.textContent = `${data.genre} Movies`;
    elements.moviesGrid.innerHTML = '';
    
    data.movies.forEach((movie, index) => {
        const card = createMovieCard(movie, index + 1);
        elements.moviesGrid.appendChild(card);
    });
}

// Display function for discover results
function displayDiscoverResults(data, contentType) {
    clearAllDisplays();
    hideAllSections();
    elements.searchResults.classList.remove('hidden');
    elements.searchTitle.textContent = contentType === 'movie' ? 'Discover Movies' : 'Discover TV Shows';
    elements.moviesGrid.innerHTML = '';
    
    data.results.forEach((item, index) => {
        const card = contentType === 'movie' ? 
            createMovieCard(item, index + 1) : 
            createTVCard(item, index + 1);
        elements.moviesGrid.appendChild(card);
    });
}

// Display function for similar TV shows
function displaySimilarTV(data) {
    clearAllDisplays();
    hideAllSections();
    elements.searchResults.classList.remove('hidden');
    elements.searchTitle.textContent = 'Similar TV Shows';
    elements.moviesGrid.innerHTML = '';
    
    if (data.items && data.items.length > 0) {
        data.items.forEach((show, index) => {
            const card = createTVCard(show, index + 1);
            elements.moviesGrid.appendChild(card);
        });
    } else {
        elements.moviesGrid.innerHTML = '<p class="no-results">No similar TV shows found</p>';
    }
}