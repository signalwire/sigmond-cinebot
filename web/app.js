// SignalWire WebRTC Configuration
const STATIC_TOKEN = 'eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2R0NNIiwidHlwIjoiU0FUIiwiY2giOiJwdWMuc2lnbmFsd2lyZS5jb20ifQ..arsTAToqHlmZIcfC.5iqzbQj5ojJlZjzKqkM1NjwX2W8XpBIVgV0R6f4irFqMuv6HWwLviXga9XoK7PAA5zeNIJtNzbAhqzwfL2vAnp8rdfj4g5beRWDs8p0pNnII7KNwC1RJ4vDAI_0chSnvngMeQ901AgxqGQ6RnoKq-fqzq-Fexq9B--lD-SRUth2U57FkQZWO6ae3O5EyaqC5G6Is7x6Lr-vXt-h6fHltriAemODYo5aVBoVMVxZc-qXd0I6sSUkuLcokd6iUoM5IPW9z-9YwjFMVV--eO0fhyYCKroR_j4kZWfgPIVNrhr4hLBwhUlGcTF4gdqcSXse7gCr74EzZSueXf-a-DooYoj_p4cYXTxh6mZSNMsg1ptDdoYUS41-NlRTsenNzbGuT5_K62eX59igL_W8VPdZ1P_bXy0ezkj_05XbUGO9P4TgOSEoBZ0Eobma_M0hFJwECkhXylrjv1WGVCseQ6-NyYX--J0o8bNs-UHpbbhNkOy1tJvn7KtT8IQZ0ud4OhgtP_V1wGC58O8b4zmTMTbCTYRRqLY65wS8bLH0mhSKM.yf0tegw6KLIb-QoPDssk-Q';
const DESTINATION = '/public/cinebot';

// Global state
let client = null;
let roomSession = null;
let isContentDisplayed = false;

// UI Elements - will be initialized after DOM loads
let elements = {};

// Initialize the app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('CineBot app initializing...');
    initializeElements();
    attachEventListeners();
    console.log('CineBot app initialized');
});

function initializeElements() {
    elements = {
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
        elements.connectBtn.textContent = 'Connect to CineBot';
        
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
    
    // Update buttons
    elements.connectBtn.style.display = 'flex';
    elements.connectBtn.disabled = false;
    elements.connectBtn.textContent = 'Connect to CineBot';
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
        case 'genre_movies':
            displayGenreMovies(eventData.data);
            break;
        case 'watch_providers':
            displayWatchProviders(eventData.data);
            break;
        case 'clear_display':
            clearAllDisplays();
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
    
    data.results.forEach(movie => {
        const card = createMovieCard(movie);
        elements.moviesGrid.appendChild(card);
    });
    
    moveAgentToCorner();
    // Audio handled by backend
}

function displayMovieDetails(details) {
    clearAllDisplays();
    hideAllSections();
    
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
    elements.castCarousel.innerHTML = '';
    
    if (data.cast && data.cast.length > 0) {
        data.cast.forEach(member => {
            const card = document.createElement('div');
            card.className = 'cast-member';
            card.innerHTML = `
                <img src="${member.profile_path || ''}" alt="${member.name}" class="cast-photo" onerror="this.src=''">
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
    elements.similarCarousel.innerHTML = '';
    
    if (data.movies && data.movies.length > 0) {
        data.movies.forEach(movie => {
            const card = createMovieCard(movie, true);
            elements.similarCarousel.appendChild(card);
        });
        
        elements.similarSection.classList.remove('hidden');
    }
}

function displayTrending(data) {
    // Clear everything first
    clearAllDisplays();
    
    // Then display trending
    hideAllSections();
    elements.searchResults.classList.remove('hidden');
    elements.searchTitle.textContent = 'Trending Movies This Week';
    elements.moviesGrid.innerHTML = '';
    
    // Display all trending movies in a grid
    if (data && data.results) {
        data.results.forEach(movie => {
            const card = createMovieCard(movie);
            elements.moviesGrid.appendChild(card);
        });
    }
    
    moveAgentToCorner();
}

function displayPersonDetails(person) {
    clearAllDisplays();
    hideAllSections();
    
    // Use the search results section to display person with all their movies
    elements.searchResults.classList.remove('hidden');
    
    // Create a header section for person info
    const headerHTML = `
        <div style="display: flex; gap: 30px; margin-bottom: 40px; padding: 20px; background: rgba(0,0,0,0.5); border-radius: 12px;">
            <img src="${person.profile_path || '/assets/no-profile.jpg'}" 
                 style="width: 200px; height: 300px; object-fit: cover; border-radius: 8px;">
            <div style="flex: 1;">
                <h2 style="font-size: 2.5rem; margin-bottom: 10px;">${person.name}</h2>
                <p style="color: var(--accent); margin-bottom: 10px;">${person.known_for_department || ''}</p>
                ${person.birthday ? `<p style="margin-bottom: 10px;">Born: ${person.birthday}${person.deathday ? ` - Died: ${person.deathday}` : ''}</p>` : ''}
                ${person.total_movie_count ? `<p style="margin-bottom: 15px;">Total Movies: ${person.total_movie_count}</p>` : ''}
                <p style="line-height: 1.6; max-height: 150px; overflow-y: auto;">${person.biography || 'No biography available.'}</p>
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
function createMovieCard(movie, isCarousel = false) {
    const card = document.createElement('div');
    card.className = 'movie-card';
    
    const poster = document.createElement('img');
    poster.src = movie.poster_path || '';
    poster.alt = movie.title;
    poster.className = 'movie-card-poster';
    poster.onerror = function() { this.style.display = 'none'; };
    
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
    // Reset the background to default
    document.body.style.backgroundImage = '';
    document.body.style.backgroundSize = '';
    document.body.style.backgroundPosition = '';
    document.body.style.backgroundAttachment = '';
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