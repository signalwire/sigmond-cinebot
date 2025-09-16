# CineBot - Your AI Movie Companion 🎬

CineBot is an intelligent voice-driven movie discovery assistant powered by SignalWire AI Agents and The Movie Database (TMDB). Have natural conversations to explore movies, actors, and get personalized recommendations with a beautiful Netflix-style visual interface.

DEMO https://cinebot.signalwire.me/

## Features

### 🎙️ Voice-First Interaction
- **Natural Language Understanding**: Talk to CineBot like you would a movie-loving friend
- **Real-time Voice Response**: Get instant spoken responses with ElevenLabs voice synthesis
- **Video Presence**: See CineBot's animated avatar during conversations
- **Context-Aware Conversations**: CineBot remembers what you're discussing and maintains context

### 🎬 Movie Discovery
- **Smart Search**: Search movies by title with automatic year filtering
  - "Show me Pretty Woman from 1990"
  - "Find Top Gun from 1986"
- **Trending Movies**: Discover what's popular this week or today
- **Genre Browsing**: Explore movies by genre (action, comedy, horror, drama, sci-fi, romance)
- **Personalized Recommendations**: Get similar movie suggestions based on what you're viewing
- **Detailed Information**: 
  - Cast and crew details with photos
  - Plot summaries and taglines
  - Release dates and runtimes
  - User ratings from TMDB
  - Content ratings (G, PG, PG-13, R, NC-17)
  - Streaming availability (Netflix, Amazon Prime, Disney+, etc.)

### 👥 Person Discovery
- **Actor/Director Search**: Find information about actors, directors, and crew
- **Complete Filmographies**: Browse all movies a person has worked on
- **Biography Information**: Learn about the person's background
- **Known For**: See their most popular works
- **Visual Profiles**: High-quality photos and headshots

### 🎯 Smart Features
- **ID-Based Selection**: CineBot uses movie and person IDs for precise selection
- **Multi-Result Handling**: When multiple matches are found, CineBot presents options
- **Watchlist Management**: Add movies to your personal watchlist
- **Automatic Trailers**: Watch trailers directly in the interface
- **Visual Placeholders**: Elegant placeholders for missing images

### 🎨 Visual Interface
- **Netflix-Style Design**: Beautiful dark theme with smooth animations
- **Responsive Layouts**: Adapts to different screen sizes
- **Rich Media Display**:
  - High-quality movie posters
  - Backdrop images with gradient overlays
  - Cast photo carousels
  - Streaming provider logos
- **Smart Positioning**: Agent video moves to corner when displaying content
- **Clean Transitions**: Smooth animations and display clearing between views

## Technical Architecture

### Backend (Python)
- **SignalWire AI Agents SDK**: Core framework for voice AI capabilities
- **TMDB Integration**: Complete movie database access via tmdbsimple
- **Redis Caching**: Fast response times with intelligent caching
- **State Management**: Context-aware conversation flow with state machines
- **SWAIG Functions**: Specialized functions for movie operations
- **Event System**: One-way event flow from backend to frontend

### Frontend (JavaScript)
- **WebRTC Video/Audio**: Real-time communication with SignalWire
- **Dynamic UI Updates**: Event-driven interface updates
- **Responsive Design**: Mobile-friendly layouts
- **Modern CSS**: Custom properties, animations, and gradients

## Installation

### Prerequisites
- Python 3.8+
- Redis server (optional, for caching)
- TMDB API key (get one at https://www.themoviedb.org/settings/api)
- SignalWire account (for production deployment)

### Setup

1. **Clone the repository**
```bash
git clone https://github.com/signalwire/sigmond-cinebot.git
cd sigmond-cinebot
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set environment variables**
```bash
export TMDB_API_KEY="your_tmdb_api_key"
export REDIS_URL="redis://localhost:6379/0"  # Optional
export PORT=3030  # Optional, defaults to 3030
```

5. **Run the application**
```bash
python cinebot_agent.py
```

6. **Access the interface**
Open your browser to `http://localhost:3030`

## Usage

### Starting a Session
1. Click "Connect to CineBot" button
2. Allow microphone and camera permissions
3. Start talking to CineBot!

### Example Conversations

**Finding Movies:**
- "Show me trending movies"
- "Search for Pretty Woman from 1990"
- "Find action movies"
- "What movies are similar to Top Gun?"

**Getting Details:**
- "Tell me about the first one"
- "Show me more details"
- "Who's in the cast?"
- "Where can I watch this?"

**Exploring People:**
- "Search for Tom Cruise"
- "Show me movies with Julia Roberts"
- "Tell me about the director"

**Navigation:**
- "Go back to trending"
- "Clear the display"
- "Show me something else"

### Voice Commands Structure

CineBot understands natural language, so speak naturally! The system recognizes:
- **Direct requests**: "Show me Star Wars"
- **Contextual references**: "Tell me about the second one"
- **Follow-up questions**: "Who directed it?"
- **Navigation**: "Go back", "Show trending again"

## API Functions

### Core SWAIG Functions

| Function | Description | Parameters |
|----------|-------------|------------|
| `search_movie` | Search for movies by title | `query` (with optional year) |
| `get_movie_details` | Get detailed movie information | `movie_id`, `movie_title`, or `search_position` |
| `search_person` | Search for actors/directors | `query`, `person_id`, or `search_position` |
| `get_trending` | Get trending movies | `time_window` (day/week) |
| `get_movies_by_genre` | Browse by genre | `genre_name` |
| `add_to_watchlist` | Add movie to watchlist | `movie_id` |
| `clear_display` | Clear the current display | None |

### Event Types

Events flow one-way from backend to frontend:

| Event | Description | Data |
|-------|-------------|------|
| `movie_search_results` | Movie search results | TMDB search results |
| `movie_details` | Detailed movie info | Movie details + cast + providers |
| `person_details` | Person information | Person details + filmography |
| `person_search_results` | Person search results | TMDB person results |
| `trending_movies` | Trending movies list | TMDB trending results |
| `genre_movies` | Movies by genre | Genre name + movies |
| `clear_display` | Clear all displays | Empty |

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TMDB_API_KEY` | TMDB API key (required) | None |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `REDIS_TTL` | Cache TTL in seconds | `3600` |
| `PORT` | Server port | `3030` |
| `HOST` | Server host | `0.0.0.0` |
| `SWML_BASIC_AUTH_USER` | Basic auth username | Auto-generated |
| `SWML_BASIC_AUTH_PASSWORD` | Basic auth password | Auto-generated |

### Customization

**Voice Settings** (in `cinebot_agent.py`):
```python
self.add_language(
    name="English",
    code="en-US", 
    voice="elevenlabs.adam"  # Change voice here
)
```

**UI Theme** (in `web/styles.css`):
- CSS custom properties for colors
- Easily customizable gradients and animations
- Responsive breakpoints

## State Management

CineBot uses a state machine with four main states:

1. **greeting**: Initial state, ready for first request
2. **browsing**: Viewing search results or lists
3. **movie_details**: Viewing specific movie information
4. **person_details**: Viewing person information

Each state has specific allowed functions and valid transitions.

## Development

### Project Structure
```
sigmond-cinebot/
├── cinebot_agent.py       # Main AI agent implementation
├── tmdb_client.py       # TMDB API client with caching
├── requirements.txt     # Python dependencies
├── web/
│   ├── index.html      # Main HTML interface
│   ├── app.js          # Frontend JavaScript
│   └── styles.css      # CSS styles
├── cinebot_idle.mp4    # Agent idle animation
├── cinebot_talking.mp4 # Agent talking animation
└── README.md           # This file
```

### Adding New Features

1. **New SWAIG Function**: Add to `_setup_functions()` in `cinebot_agent.py`
2. **New Event Type**: Add handler in `handleAgentEvent()` in `app.js`
3. **New Display Mode**: Create display function in `app.js`
4. **New State**: Add to state machine in `cinebot_agent.py`

### Testing
```bash
# Run with debug logging
python cinebot_agent.py

# Test TMDB connection
python -c "from tmdb_client import TMDBClient; client = TMDBClient(); print(client.search_movie('Star Wars'))"

# Monitor Redis cache
redis-cli MONITOR
```

## Deployment

### SignalWire Deployment

1. Set up SignalWire account
2. Configure environment variables
3. Deploy to SignalWire-compatible hosting
4. Update webhook URLs in SignalWire dashboard

### Docker Deployment
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "cinebot_agent.py"]
```

## Troubleshooting

### Common Issues

**"401 Unauthorized" errors**
- Check basic auth credentials in startup logs
- Verify SignalWire configuration

**No movies displaying**
- Check browser console for JavaScript errors
- Verify TMDB API key is valid
- Check Redis connection

**Voice not working**
- Ensure microphone permissions granted
- Check WebRTC connection in browser console
- Verify SignalWire credentials

**Display not clearing properly**
- Hard refresh browser (Ctrl+Shift+R)
- Check for JavaScript errors
- Verify event handlers are registered

## Key Improvements Made

### Year-Based Search
- Automatically parses year from queries like "Pretty Woman from 1990"
- Filters results to match the specified year
- Provides clear feedback when movies from specific years aren't found

### ID Exposure for AI
- All search results now include movie/person IDs in the response text
- Format: `"id: 114 title: 'Pretty Woman' (1990)"`
- Enables precise selection without ambiguity

### Display Management
- All display functions properly clear previous content
- Prevents overlapping or stuck displays
- Smooth transitions between different views

### Authentication
- Proper basic auth setup with auto-generated credentials
- Credentials displayed on startup for easy access
- Secure WebRTC communication

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

MIT License - See LICENSE file for details

## Credits

- **SignalWire** - AI Agent platform and WebRTC infrastructure
- **The Movie Database (TMDB)** - Movie data and images
- **ElevenLabs** - Voice synthesis
- **Redis** - Caching layer
- **Holy Guacamole** - Architecture inspiration

## Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Contact the development team
- Check the SignalWire documentation

---

Built with ❤️ for movie lovers everywhere