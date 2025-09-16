#!/usr/bin/env python3
import os
import json
import logging
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from signalwire_agents import AgentBase, SwaigFunctionResult
from tmdb_client import TMDBClient

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MovieAgent(AgentBase):
    def __init__(self):
        super().__init__(
            name="CineBot Movie Assistant",
            route="/swml"  # SWML endpoint path
        )
        
        # Initialize TMDB client
        self.tmdb = TMDBClient(
            api_key=os.getenv("TMDB_API_KEY"),
            redis_url=os.getenv("REDIS_URL")
        )
        
        # Order state tracking
        self.current_search_results = []
        self.search_result_mapping = {}  # Maps position to movie/TV details with IDs
        self.person_search_mapping = {}  # Maps position to person details with IDs
        self.last_search_info = ""  # Info about last search for AI reference
        self.last_person_search_info = ""  # Info about last person search
        self.current_movie_id = None
        self.current_person_id = None
        self.current_tv_id = None
        self.watchlist = []
        
        # Setup agent configuration
        self._setup_agent()
        self._setup_functions()
    
    def _setup_agent(self):
        """Configure agent personality and conversation contexts"""
        
        # Set avatar videos (will be dynamically updated with full URLs)
        self.set_param("video_idle_file", "/cinebot_idle.mp4")
        self.set_param("video_talking_file", "/cinebot_talking.mp4")
        
        # Agent personality
        self.set_param("voice_id", "en-US-Standard-J")
        self.set_param("voice_pitch", "-2st")
        self.set_param("voice_rate", "95%")
        
        # Greeting message
        self.set_param("greeting_text", 
            "Hello! I'm CineBot, your personal entertainment expert. "
            "I can help you discover movies and TV shows, learn about actors, "
            "find trending content, or explore different genres. "
            "What movie, TV show, or actor would you like to know about?"
        )
        
        # Set initial background display
        self.set_param("initial_background", "/background.png")
        
        # Configure voice
        self.add_language(
            name="English",
            code="en-US",
            voice="elevenlabs.adam"
        )
        
        # Add speech hints for better recognition
        self.add_hints([
            "movie", "film", "actor", "actress", "director",
            "TV", "show", "series", "season", "episode",
            "trailer", "cast", "crew", "genre", "rating",
            "search", "find", "tell", "about",
            "trending", "popular", "similar", "recommend",
            "watch", "stream", "netflix", "amazon", "disney",
            "yes", "no", "more", "details", "back"
        ])
        
        # Define conversation contexts with state machine
        contexts = self.define_contexts()
        
        default_context = contexts.add_context("default") \
            .add_section("Goal", "Help users discover and learn about movies, TV shows, actors, and entertainment.")
        
        # GREETING STATE - Entry point
        default_context.add_step("greeting") \
            .add_section("Current Task", "Welcome the user and understand what they want to explore") \
            .add_bullets("Available Actions", [
                "Search for movies by title",
                "Search for TV shows by title",
                "Search for actors or directors",
                "Show trending movies or TV shows",
                "Browse by genre",
                "Clear the display"
            ]) \
            .set_step_criteria("User has made an initial request") \
            .set_functions([
                "multi_search", "search_movie", "search_tv", "search_person",
                "get_trending", "get_trending_tv", "get_movies_by_genre",
                "get_now_playing", "discover_content", "clear_display"
            ]) \
            .set_valid_steps(["browsing", "movie_details", "tv_details", "person_details"])
        
        # BROWSING STATE - After search results
        default_context.add_step("browsing") \
            .add_section("Current Task", "User is browsing search results") \
            .add_section("CRITICAL RULE", "CHECK self.last_search_info which contains movie/TV IDs for each position! When user says 'first one', use search_position=1. ALWAYS use the ID from self.last_search_info or search_position parameter.") \
            .add_bullets("Available Actions", [
                "Get details about a specific movie or TV show",
                "Search for more movies or TV shows",
                "Search for people",
                "View trending content",
                "Browse genres",
                "Add to watchlist"
            ]) \
            .set_step_criteria("User wants to explore specific content") \
            .set_functions([
                "multi_search", "search_movie", "search_tv", "get_movie_details",
                "get_tv_details", "search_person", "get_trending", "get_trending_tv",
                "get_movies_by_genre", "discover_content", "clear_display",
                "add_to_watchlist"
            ]) \
            .set_valid_steps(["movie_details", "tv_details", "person_details", "greeting"])
        
        # MOVIE DETAILS STATE - Viewing specific movie
        default_context.add_step("movie_details") \
            .add_section("Current Task", "User is viewing movie details") \
            .add_bullets("Available Actions", [
                "Show cast and crew",
                "Find similar movies",
                "Play trailer",
                "Add to watchlist",
                "Search for other content"
            ]) \
            .set_step_criteria("User wants more information about the movie") \
            .set_functions([
                "get_cast_crew", "get_similar_content", "get_videos",
                "add_to_watchlist", "search_movie", "search_person",
                "clear_display"
            ]) \
            .set_valid_steps(["browsing", "person_details", "greeting"])
        
        # TV DETAILS STATE - Viewing specific TV show
        default_context.add_step("tv_details") \
            .add_section("Current Task", "User is viewing TV show details") \
            .add_bullets("Available Actions", [
                "Show cast and crew",
                "Explore seasons and episodes",
                "Find similar TV shows",
                "Play trailer",
                "Add to watchlist",
                "Search for other content"
            ]) \
            .set_step_criteria("User wants more information about the TV show") \
            .set_functions([
                "get_cast_crew", "get_season_details", "get_similar_content",
                "get_videos", "add_to_watchlist", "search_movie", "search_tv",
                "search_person", "clear_display"
            ]) \
            .set_valid_steps(["browsing", "person_details", "greeting"])
        
        # PERSON DETAILS STATE - Viewing actor/director
        default_context.add_step("person_details") \
            .add_section("Current Task", "User is viewing person details") \
            .add_section("CRITICAL RULE", "The person's filmography contains movie IDs. When user wants a movie from the filmography, use get_movie_details with the movie_id from the displayed films.") \
            .add_bullets("Available Actions", [
                "Get movie details from filmography (use movie IDs)",
                "Search for other people",
                "Search for movies",
                "Clear and start over"
            ]) \
            .set_step_criteria("User wants to explore other content") \
            .set_functions([
                "get_movie_details", "search_movie", "search_person",
                "clear_display"
            ]) \
            .set_valid_steps(["movie_details", "browsing", "greeting"])
        
        # Agent prompts
        self.prompt_add_section(
            "personality",
            "You are CineBot, a passionate entertainment enthusiast with encyclopedic "
            "knowledge of movies and TV shows. You're excited to share recommendations, "
            "trivia, and help users discover great content. You have a friendly, "
            "engaging personality and love discussing both films and television."
        )
        
        self.prompt_add_section(
            "instructions",
            "CRITICAL CONTENT SELECTION RULES:\n"
            "1. ALWAYS search first before calling get_movie_details or get_tv_details\n"
            "2. After search, CHECK self.last_search_info which has IDs for each position!\n"
            "3. When user selects content:\n"
            "   - 'first one' or 'number 1' → use appropriate get_details(search_position=1)\n"
            "   - By name → find it in self.last_search_info, get its ID\n"
            "   - 'the second one' → use get_details(search_position=2)\n"
            "4. Distinguish between movies and TV shows:\n"
            "   - Movies: use search_movie and get_movie_details\n"
            "   - TV shows: use search_tv and get_tv_details\n"
            "5. When user selects a person:\n"
            "   - Check self.last_person_search_info for person IDs\n"
            "   - Use search_person(search_position=N) or search_person(person_id=XXX)\n"
            "6. For multi-search results:\n"
            "   - Check the type field in search_result_mapping\n"
            "   - Use get_movie_details for movies, get_tv_details for TV, search_person for people\n"
            "7. ALWAYS use either ID or search_position parameters\n"
            "8. NEVER mention IDs to the user - they are for internal use only\n"
            "\n"
            "USER INTERACTION RULES:\n"
            "- NEVER show IDs to users in responses - keep them internal\n"
            "- Check self.last_search_info to get the correct ID\n"
            "- When presenting results, show title/name and year only\n" 
            "- If search returns no results, try searching with fewer words\n"
            "- Clear the display before showing new content\n"
            "- Offer relevant options based on content type (seasons for TV, trailers for movies)\n"
            "- When user asks for content with filters (year, genre, rating), use discover_content\n"
            "- When user asks general search without specifying type, use multi_search"
        )
        
        self.prompt_add_section(
            "error_handling",
            "If a movie or person search returns no results, suggest alternatives or "
            "ask for clarification. If an API error occurs, apologize briefly and "
            "suggest trying again or searching for something else."
        )
    
    def _setup_functions(self):
        """Register SWAIG functions for movie operations"""
        
        @self.tool(
            name="search_movie",
            description="Search for movies by title",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The movie title to search for"
                    }
                },
                "required": ["query"]
            }
        )
        def search_movie(args, raw_data):
            query = args.get("query", "").strip()
            logger.info(f"search_movie called with query: '{query}'")
            
            if not query:
                return SwaigFunctionResult(
                    response="Please provide a movie title to search for."
                )
            
            # Parse out year from query if present
            import re
            year_match = re.search(r'(from |in )?(\d{4})', query, re.IGNORECASE)
            search_query = query
            year_filter = None
            
            if year_match:
                year_filter = year_match.group(2)
                # Remove the year phrase from the search query
                search_query = re.sub(r'(from |in )?\d{4}', '', query, flags=re.IGNORECASE).strip()
                logger.info(f"Parsed query: title='{search_query}', year={year_filter}")
            
            try:
                results = self.tmdb.search_movie(search_query)
                logger.info(f"TMDB returned {len(results.get('results', []))} results for '{search_query}'")
                self.current_search_results = results["results"]
                
                # If no results, try alternative search strategies
                if not results["results"] and len(search_query) > 2:
                    logger.info(f"No results for '{search_query}', trying alternative search strategies")
                    
                    # Try searching without common words
                    alt_query = re.sub(r'\b(the|a|an)\b', '', search_query, flags=re.IGNORECASE).strip()
                    if alt_query != search_query:
                        results = self.tmdb.search_movie(alt_query)
                        logger.info(f"Alternative search '{alt_query}' returned {len(results.get('results', []))} results")
                        self.current_search_results = results["results"]
                
                if results["results"]:
                    # Filter by year if specified
                    filtered_results = results["results"]
                    if year_filter:
                        filtered_results = [
                            m for m in results["results"]
                            if m.get('release_date', '').startswith(year_filter)
                        ]
                        logger.info(f"Filtered to {len(filtered_results)} results for year {year_filter}")
                    
                    if not filtered_results:
                        return SwaigFunctionResult(
                            response=f"I couldn't find '{search_query}' from {year_filter}. "
                            f"Try searching without the year or check if the year is correct."
                        )
                    
                    # Build more detailed movie list and store mapping for AI
                    movie_descriptions = []
                    self.search_result_mapping = {}  # Reset mapping
                    
                    for i, m in enumerate(filtered_results[:24], 1):  # Show more results for better matching
                        year = m.get('release_date', '')[:4] if m.get('release_date') else 'unknown year'
                        # Include ID directly in the response text for LLM to see
                        movie_descriptions.append(f"{i}. id: {m['id']} title: '{m['title']}' ({year})")
                        
                        # Store mapping for AI to use internally
                        self.search_result_mapping[i] = {
                            "id": m['id'],
                            "title": m['title'],
                            "year": year,
                            "overview": m.get('overview', '')[:100]
                        }
                    
                    # Store the filtered results for later reference
                    self.current_search_results = filtered_results
                    
                    # Create info for AI about the search results with IDs
                    self.last_search_info = f"SEARCH RESULTS WITH IDS for '{query}':\n"
                    for pos, info in self.search_result_mapping.items():
                        self.last_search_info += f"  Position {pos}: {info['title']} ({info['year']}) -> movie_id={info['id']}\n"
                    
                    # Log the mapping so we can debug
                    logger.info(f"Search mapping: {self.last_search_info}")
                    
                    result = SwaigFunctionResult(
                        response=f"I found {len(filtered_results)} movies matching '{search_query}'"
                        f"{f' from {year_filter}' if year_filter else ''}. "
                        f"Here are the results:\n{chr(10).join(movie_descriptions)}\n"
                        f"Which movie would you like to know more about?"
                    )
                else:
                    result = SwaigFunctionResult(
                        response=f"I couldn't find any movies matching '{query}'. "
                        f"Try searching with a different title or let me show you trending movies."
                    )
                
                # Send event to frontend (frontend will clear display when handling this)
                logger.info(f"Sending movie_search_results event with {len(results['results'])} movies")
                result.swml_user_event({
                    "type": "movie_search_results",
                    "data": results
                })
                
                # Transition to browsing state
                result.swml_change_step("browsing")
                logger.info("Transitioned to browsing state")
                
                return result
            except Exception as e:
                logger.error(f"Error searching movies: {e}")
                return SwaigFunctionResult(
                    response="I encountered an error searching for movies. Please try again."
                )
        
        @self.tool(
            name="get_movie_details",
            description="Get detailed information about a specific movie",
            parameters={
                "type": "object",
                "properties": {
                    "movie_title": {
                        "type": "string",
                        "description": "The title of the movie (optional if movie_id provided)"
                    },
                    "movie_id": {
                        "type": "integer",
                        "description": "The TMDB ID of the movie (preferred - use this from search results)"
                    },
                    "search_position": {
                        "type": "integer",
                        "description": "Position in search results (1-based index, e.g., 1 for first result)"
                    }
                },
                "required": []
            }
        )
        def get_movie_details(args, raw_data):
            movie_id = args.get("movie_id")
            movie_title = args.get("movie_title")
            search_position = args.get("search_position")
            logger.info(f"get_movie_details called with movie_id={movie_id}, movie_title={movie_title}, search_position={search_position}")
            
            # Priority 1: Use movie_id if provided
            if movie_id:
                logger.info(f"Using provided movie_id: {movie_id}")
            
            # Priority 2: Use search position if provided
            elif search_position and self.search_result_mapping:
                if search_position in self.search_result_mapping:
                    movie_info = self.search_result_mapping[search_position]
                    movie_id = movie_info["id"]
                    movie_title = movie_info["title"]
                    logger.info(f"Selected movie at position {search_position}: '{movie_title}' (ID: {movie_id})")
                else:
                    logger.warning(f"Position {search_position} not found in search results")
            
            # Priority 3: Try to match from current search results
            elif movie_title and self.current_search_results:
                logger.info(f"Matching '{movie_title}' from current search results")
                import re
                
                # Extract year if present in title
                year_match = re.search(r'\b(19\d{2}|20\d{2})\b', movie_title)
                requested_year = year_match.group(1) if year_match else None
                
                # Clean title for matching
                clean_title = re.sub(r'\b(19\d{2}|20\d{2})\b', '', movie_title).strip()
                clean_title = re.sub(r'[^\w\s]', '', clean_title).lower()
                
                # Find best match from current results
                best_match = None
                best_score = 0
                
                for movie in self.current_search_results:
                    score = 0
                    movie_clean = re.sub(r'[^\w\s]', '', movie["title"]).lower()
                    
                    # Exact title match
                    if movie_clean == clean_title:
                        score += 100
                    elif clean_title in movie_clean or movie_clean in clean_title:
                        score += 50
                    
                    # Year match
                    if requested_year and requested_year in movie.get("release_date", ""):
                        score += 50
                    
                    if score > best_score:
                        best_score = score
                        best_match = movie
                
                if best_match:
                    movie_id = best_match["id"]
                    logger.info(f"Best match from search results: '{best_match['title']}' (ID: {movie_id}, score: {best_score})")
            
            # Priority 4: Do a fresh search if we still don't have an ID
            if not movie_id and movie_title:
                logger.info(f"No movie_id provided, searching for '{movie_title}'")
                import re
                
                # ALWAYS do a fresh search to ensure we have the right data
                # Extract year if present
                year_match = re.search(r'\b(19\d{2}|20\d{2})\b', movie_title)
                requested_year = year_match.group(1) if year_match else None
                
                # Clean title for searching
                clean_title = re.sub(r'\b(19\d{2}|20\d{2})\b', '', movie_title)
                clean_title = re.sub(r'\b(with|starring|julia roberts|richard gere|julia|roberts|gere|from|the|one)\b', '', clean_title, flags=re.IGNORECASE)
                clean_title = clean_title.strip()
                
                logger.info(f"Searching for clean title: '{clean_title}', requested year: {requested_year}")
                
                # Always search fresh to get consistent results
                search_results = self.tmdb.search_movie(clean_title)
                
                if search_results["results"]:
                    # Special handling for Pretty Woman - ALWAYS get the 1990 version unless specified otherwise
                    if "pretty woman" in clean_title.lower():
                        # Default to 1990 version
                        for movie in search_results["results"]:
                            if "1990" in movie.get("release_date", ""):
                                movie_id = movie["id"]
                                logger.info(f"Selected Pretty Woman 1990 (default) with ID {movie_id}")
                                break
                        # Only use a different version if year is explicitly different
                        if requested_year and requested_year != "1990":
                            for movie in search_results["results"]:
                                if requested_year in movie.get("release_date", ""):
                                    movie_id = movie["id"]
                                    logger.info(f"Selected Pretty Woman {requested_year} (requested) with ID {movie_id}")
                                    break
                    else:
                        # For other movies, use simple scoring
                        best_match = None
                        best_score = 0
                        
                        for movie in search_results["results"]:
                            score = 0
                            
                            # Title match
                            if movie["title"].lower() == clean_title.lower():
                                score += 20
                            elif clean_title.lower() in movie["title"].lower():
                                score += 10
                            
                            # Year match is most important if specified
                            if requested_year and movie.get("release_date"):
                                if requested_year in movie["release_date"]:
                                    score += 50  # Heavy weight for year match
                            
                            # Use popularity as tiebreaker only
                            if score > 0:
                                score += min(movie.get("popularity", 0) / 100, 2)
                            
                            if score > best_score:
                                best_score = score
                                best_match = movie
                        
                        if best_match:
                            movie_id = best_match["id"]
                            logger.info(f"Selected {best_match['title']} ({best_match.get('release_date', 'N/A')[:4]}) with ID {movie_id} (score: {best_score})")
                        elif search_results["results"]:
                            # Fallback to first result if no good match
                            movie_id = search_results["results"][0]["id"]
                            logger.info(f"No good match, using first result: {search_results['results'][0]['title']}")
            
            if not movie_id:
                result = SwaigFunctionResult(
                    response="Please specify which movie you'd like details about."
                )
                return result
            
            try:
                details = self.tmdb.get_movie_details(movie_id)
                self.current_movie_id = movie_id
                
                # Build response
                genres = ", ".join(details["genres"][:3])
                runtime_hours = details["runtime"] // 60
                runtime_mins = details["runtime"] % 60
                
                response = f"Here's {details['title']} from {details['release_date'][:4] if details['release_date'] else 'unknown year'}. "
                
                if details["tagline"]:
                    response += f"\"{details['tagline']}\". "
                
                response += f"It's a {genres} film that runs {runtime_hours} hours and {runtime_mins} minutes. "
                response += f"The movie has a rating of {details['vote_average']:.1f} out of 10. "
                
                if details["overview"]:
                    response += f"Here's what it's about: {details['overview'][:200]}... "
                
                # Check if trailer is available before offering it
                has_trailer = False
                if details.get("videos"):
                    has_trailer = any(v["type"] == "Trailer" for v in details["videos"])
                
                # Build options based on available content
                options = []
                if has_trailer:
                    options.append("play the trailer")
                options.append("find similar movies")
                options.append("tell you about the cast members shown on screen")
                
                response += f"You can ask me to {', or '.join(options)}."
                
                result = SwaigFunctionResult(response=response)
                
                # Get watch provider information and add to details
                try:
                    providers = self.tmdb.get_watch_providers(movie_id)
                    if providers:
                        details["watch_providers"] = providers
                        logger.info(f"Added {len(providers.get('providers', []))} watch providers to details")
                except Exception as e:
                    logger.error(f"Error getting watch providers: {e}")
                    details["watch_providers"] = None
                
                # Send event to frontend with all details including providers (frontend will clear display)
                event_data = {
                    "type": "movie_details",
                    "data": details
                }
                logger.info(f"Sending movie_details event for '{details['title']}'")
                result.swml_user_event(event_data)
                
                # Transition to movie_details state
                result.swml_change_step("movie_details")
                logger.info("Transitioned to movie_details state")
                
                return result
                
            except Exception as e:
                logger.error(f"Error getting movie details: {e}")
                result = SwaigFunctionResult(
                    response="I couldn't fetch the movie details. Please try again."
                )
                return result
        
        @self.tool(
            name="get_cast_crew",
            description="Get cast and crew information for a movie or TV show",
            parameters={
                "type": "object",
                "properties": {
                    "content_id": {
                        "type": "integer",
                        "description": "The ID of the movie or TV show (uses current if not provided)"
                    },
                    "content_type": {
                        "type": "string",
                        "description": "Type of content",
                        "enum": ["movie", "tv"]
                    }
                },
                "required": []
            }
        )
        def get_cast_crew(args, raw_data):
            # Determine content type and ID
            content_type = args.get("content_type")
            content_id = args.get("content_id")
            
            # Auto-detect based on current state if not provided
            if not content_type:
                if self.current_movie_id:
                    content_type = "movie"
                    content_id = content_id or self.current_movie_id
                elif self.current_tv_id:
                    content_type = "tv"
                    content_id = content_id or self.current_tv_id
                else:
                    return SwaigFunctionResult(
                        response="Please select a movie or TV show first to see its cast and crew."
                    )
            else:
                if content_type == "movie":
                    content_id = content_id or self.current_movie_id
                else:
                    content_id = content_id or self.current_tv_id
            
            if not content_id:
                result = SwaigFunctionResult(
                    response=f"Please select a {'movie' if content_type == 'movie' else 'TV show'} first to see its cast and crew."
                )
                return result
            
            try:
                # Get details based on content type
                if content_type == "movie":
                    details = self.tmdb.get_movie_details(content_id)
                else:
                    details = self.tmdb.get_tv_details(content_id)
                
                cast_crew = {
                    "cast": details.get("cast", []),
                    "crew": details.get("crew", [])
                }
                
                # Build response - store cast IDs for voice navigation
                top_cast = cast_crew["cast"][:5]
                cast_descriptions = []
                self.person_search_mapping = {}  # Reset person mapping for voice selection
                
                for i, actor in enumerate(top_cast, 1):
                    if content_type == "movie":
                        cast_descriptions.append(f"{actor['name']} as {actor.get('character', 'Unknown')}")
                    else:
                        # TV shows might have roles instead of character
                        cast_descriptions.append(f"{actor['name']} as {actor.get('character', actor.get('roles', [{}])[0].get('character', 'Unknown'))}")
                    
                    # Store mapping for voice selection
                    self.person_search_mapping[i] = {
                        "id": actor["id"],
                        "name": actor["name"],
                        "character": actor.get("character", "")
                    }
                
                # Find key crew members
                if content_type == "movie":
                    director = next((c for c in cast_crew["crew"] if c["job"] == "Director"), None)
                    producer = next((c for c in cast_crew["crew"] if c["job"] == "Producer"), None)
                    writer = next((c for c in cast_crew["crew"] if "Writer" in c.get("job", "") or "Screenplay" in c.get("job", "")), None)
                else:
                    # TV shows have creators instead of directors
                    creators = details.get("created_by", [])
                    executive_producers = [c for c in cast_crew["crew"] if c["job"] == "Executive Producer"][:2]
                
                # Build voice-friendly response
                response = f"Here's the cast and crew for {details.get('title', details.get('name', 'this content'))}. "
                
                if cast_descriptions:
                    response += f"The main cast includes: {', '.join(cast_descriptions[:3])}. "
                    if len(cast_descriptions) > 3:
                        response += f"Also featuring {', '.join([actor['name'] for actor in top_cast[3:5]])}. "
                
                if content_type == "movie":
                    if director:
                        response += f"Directed by {director['name']}. "
                    if writer:
                        response += f"Written by {writer['name']}. "
                    if producer:
                        response += f"Produced by {producer['name']}. "
                else:
                    if creators:
                        response += f"Created by {', '.join([c['name'] for c in creators[:2]])}. "
                    if executive_producers:
                        response += f"Executive produced by {', '.join([p['name'] for p in executive_producers])}. "
                
                response += "Would you like to know more about any of these people?"
                
                # Update last person search info for AI
                self.last_person_search_info = f"CAST MEMBERS WITH IDS:\n"
                for pos, info in self.person_search_mapping.items():
                    self.last_person_search_info += f"  Position {pos}: {info['name']} -> person_id={info['id']}\n"
                
                logger.info(f"Cast mapping: {self.last_person_search_info}")
                
                result = SwaigFunctionResult(response=response)
                
                # Check if this is a different movie/show than what's currently displayed
                # If so, send full details instead of just cast
                should_update_full_display = False
                if content_type == "movie" and content_id != self.current_movie_id:
                    should_update_full_display = True
                    self.current_movie_id = content_id
                    self.current_tv_id = None
                elif content_type == "tv" and content_id != self.current_tv_id:
                    should_update_full_display = True
                    self.current_tv_id = content_id
                    self.current_movie_id = None
                
                if should_update_full_display:
                    # Send full movie/TV details event to update entire display
                    event_type = "movie_details" if content_type == "movie" else "tv_details"
                    result.swml_user_event({
                        "type": event_type,
                        "data": details
                    })
                    
                    # Also change state
                    if content_type == "movie":
                        result.swml_change_step("movie_details")
                    else:
                        result.swml_change_step("tv_details")
                else:
                    # Just update cast section if it's the same content
                    result.swml_user_event({
                        "type": "cast_crew_display",
                        "data": cast_crew
                    })
                
                return result
                
            except Exception as e:
                logger.error(f"Error getting cast/crew: {e}")
                result = SwaigFunctionResult(
                    response="I couldn't fetch the cast information. Please try again."
                )
                return result
        
        @self.tool(
            name="get_now_playing",
            description="Get movies currently playing in theaters",
            parameters={
                "type": "object",
                "properties": {
                    "region": {
                        "type": "string",
                        "description": "Country code (e.g., 'US', 'UK', 'CA')",
                        "default": "US"
                    }
                },
                "required": []
            }
        )
        def get_now_playing(args, raw_data):
            region = args.get("region", "US")
            logger.info(f"get_now_playing called for region: {region}")
            
            try:
                results = self.tmdb.get_now_playing(region=region)
                
                if results["results"]:
                    movie_list = []
                    self.search_result_mapping = {}  # Use same mapping as search
                    
                    for i, m in enumerate(results["results"][:24], 1):
                        year = m.get('release_date', '')[:4] if m.get('release_date') else ''
                        movie_list.append(f"{i}. '{m['title']}' ({year}) - Rating: {m['vote_average']:.1f}/10")
                        
                        # Store mapping for AI
                        self.search_result_mapping[i] = {
                            "id": m['id'],
                            "title": m['title'],
                            "year": year
                        }
                    
                    response = f"Here are the movies currently playing in theaters"
                    if region != "US":
                        response += f" in {region}"
                    response += f":\n{chr(10).join(movie_list)}\n"
                    response += "Which movie would you like to know more about?"
                    
                    result = SwaigFunctionResult(response=response)
                    
                    # Send event to frontend
                    result.swml_user_event({
                        "type": "now_playing",
                        "data": results
                    })
                    
                    # Transition to browsing state
                    result.swml_change_step("browsing")
                    
                    return result
                else:
                    return SwaigFunctionResult(
                        response="I couldn't find any movies currently playing in theaters. Try checking trending movies instead."
                    )
                    
            except Exception as e:
                logger.error(f"Error getting now playing: {e}")
                return SwaigFunctionResult(
                    response="I had trouble getting current theater listings. Let me show you trending movies instead."
                )
        
        @self.tool(
            name="get_similar_content", 
            description="Find similar movies or TV shows to the current one",
            parameters={
                "type": "object",
                "properties": {
                    "content_id": {
                        "type": "integer",
                        "description": "The ID of the movie or TV show (uses current if not provided)"
                    },
                    "content_type": {
                        "type": "string",
                        "description": "Type of content",
                        "enum": ["movie", "tv"]
                    }
                },
                "required": []
            }
        )
        def get_similar_content(args, raw_data):
            # Determine content type and ID
            content_type = args.get("content_type")
            content_id = args.get("content_id")
            
            # Auto-detect based on current state if not provided
            if not content_type:
                if self.current_movie_id:
                    content_type = "movie"
                    content_id = content_id or self.current_movie_id
                elif self.current_tv_id:
                    content_type = "tv"
                    content_id = content_id or self.current_tv_id
                else:
                    return SwaigFunctionResult(
                        response="Please select a movie or TV show first to find similar content."
                    )
            else:
                if content_type == "movie":
                    content_id = content_id or self.current_movie_id
                else:
                    content_id = content_id or self.current_tv_id
            
            if not content_id:
                result = SwaigFunctionResult(
                    response=f"Please select a {'movie' if content_type == 'movie' else 'TV show'} first to find similar ones."
                )
                return result
            
            try:
                # Use the new recommendations endpoint (ML-based, better than similar)
                recommendations = self.tmdb.get_recommendations(content_id, content_type)
                
                # Fallback to similar if no recommendations
                if not recommendations.get("results"):
                    if content_type == "movie":
                        details = self.tmdb.get_movie_details(content_id)
                        similar = details.get("similar", [])
                        content_name = details['title']
                    else:
                        details = self.tmdb.get_tv_details(content_id)
                        similar = details.get("similar", [])
                        content_name = details['name']
                else:
                    similar = recommendations["results"]
                    # Get content name for response
                    if content_type == "movie":
                        details = self.tmdb.get_movie_details(content_id)
                        content_name = details['title']
                    else:
                        details = self.tmdb.get_tv_details(content_id)
                        content_name = details['name']
                
                if similar:
                    # Build descriptions and store mapping for voice selection
                    descriptions = []
                    self.search_result_mapping = {}
                    
                    for i, item in enumerate(similar[:8], 1):  # Show more results for voice
                        if content_type == "movie":
                            year = item.get('release_date', '')[:4] if item.get('release_date') else ''
                            title = item['title']
                            rating = item.get('vote_average', 0)
                            descriptions.append(f"{i}. {title} ({year}) - {rating:.1f}⭐")
                            
                            self.search_result_mapping[i] = {
                                "type": "movie",
                                "id": item['id'],
                                "title": title,
                                "year": year
                            }
                        else:
                            year = item.get('first_air_date', '')[:4] if item.get('first_air_date') else ''
                            name = item['name']
                            rating = item.get('vote_average', 0)
                            descriptions.append(f"{i}. {name} ({year}) - {rating:.1f}⭐")
                            
                            self.search_result_mapping[i] = {
                                "type": "tv",
                                "id": item['id'],
                                "name": name,
                                "year": year
                            }
                    
                    response = f"Based on {content_name}, you might enjoy these similar {'movies' if content_type == 'movie' else 'TV shows'}:\n"
                    response += "\n".join(descriptions[:6]) + "\n"  # Voice-friendly, not too many
                    response += f"Which one would you like to know more about?"
                    
                    # Update last search info for AI voice navigation
                    self.last_search_info = f"SIMILAR CONTENT WITH IDS:\n"
                    for pos, info in self.search_result_mapping.items():
                        if info['type'] == 'movie':
                            self.last_search_info += f"  Position {pos}: {info['title']} ({info['year']}) -> movie_id={info['id']}\n"
                        else:
                            self.last_search_info += f"  Position {pos}: {info['name']} ({info['year']}) -> tv_id={info['id']}\n"
                    
                    logger.info(f"Similar content mapping: {self.last_search_info}")
                else:
                    response = f"I couldn't find similar {'movies' if content_type == 'movie' else 'TV shows'} for this title."
                
                result = SwaigFunctionResult(response=response)
                
                # Send event to frontend
                result.swml_user_event({
                    "type": f"similar_{content_type}",
                    "data": {"items": similar}
                })
                
                # Transition to browsing state for selection
                if similar:
                    result.swml_change_step("browsing")
                
                return result
                
            except Exception as e:
                logger.error(f"Error getting similar content: {e}")
                result = SwaigFunctionResult(
                    response="I couldn't fetch similar content. Please try again."
                )
                return result
        
        @self.tool(
            name="get_videos",
            description="Get trailers and video clips for a movie or TV show",
            parameters={
                "type": "object",
                "properties": {
                    "content_id": {
                        "type": "integer",
                        "description": "The ID of the movie or TV show (uses current if not provided)"
                    },
                    "content_type": {
                        "type": "string",
                        "description": "Type of content",
                        "enum": ["movie", "tv"]
                    },
                    "video_type": {
                        "type": "string",
                        "description": "Type of video to show",
                        "enum": ["trailer", "teaser", "clip", "behind_the_scenes", "all"]
                    }
                },
                "required": []
            }
        )
        def get_videos(args, raw_data):
            # Determine content type and ID
            content_type = args.get("content_type")
            content_id = args.get("content_id")
            video_type = args.get("video_type", "trailer")
            
            # Auto-detect based on current state if not provided
            if not content_type:
                if self.current_movie_id:
                    content_type = "movie"
                    content_id = content_id or self.current_movie_id
                elif self.current_tv_id:
                    content_type = "tv"
                    content_id = content_id or self.current_tv_id
                else:
                    return SwaigFunctionResult(
                        response="Please select a movie or TV show first to see its videos."
                    )
            else:
                if content_type == "movie":
                    content_id = content_id or self.current_movie_id
                else:
                    content_id = content_id or self.current_tv_id
            
            if not content_id:
                result = SwaigFunctionResult(
                    response=f"Please select a {'movie' if content_type == 'movie' else 'TV show'} first to see its videos."
                )
                return result
            
            try:
                # Get details with videos
                if content_type == "movie":
                    details = self.tmdb.get_movie_details(content_id)
                    content_name = details['title']
                else:
                    details = self.tmdb.get_tv_details(content_id)
                    content_name = details['name']
                
                videos = details.get("videos", [])
                
                # Filter by type if specified
                if video_type == "all":
                    filtered_videos = videos
                elif video_type == "trailer":
                    filtered_videos = [v for v in videos if v["type"] == "Trailer"]
                elif video_type == "teaser":
                    filtered_videos = [v for v in videos if v["type"] == "Teaser"]
                elif video_type == "clip":
                    filtered_videos = [v for v in videos if v["type"] in ["Clip", "Featurette"]]
                elif video_type == "behind_the_scenes":
                    filtered_videos = [v for v in videos if v["type"] in ["Behind the Scenes", "Featurette"]]
                else:
                    filtered_videos = [v for v in videos if v["type"] == "Trailer"]
                
                if filtered_videos:
                    # Describe available videos for voice navigation
                    if len(filtered_videos) == 1:
                        video = filtered_videos[0]
                        response = f"I found a {video['type'].lower()} for {content_name}: '{video['name']}'. "
                        response += "It's now playing on your screen."
                        
                        # Send single video
                        result = SwaigFunctionResult(response=response)
                        result.swml_user_event({
                            "type": "video_available",
                            "data": {"video": video, "all_videos": filtered_videos}
                        })
                    else:
                        # Multiple videos - let user choose via voice
                        video_list = []
                        for i, v in enumerate(filtered_videos[:5], 1):  # Limit for voice
                            video_list.append(f"{i}. {v['type']}: {v['name']}")
                        
                        response = f"I found {len(filtered_videos)} videos for {content_name}:\n"
                        response += "\n".join(video_list)
                        response += "\nThe first one is playing now. Would you like to see a different one?"
                        
                        # Send all videos, play first
                        result = SwaigFunctionResult(response=response)
                        result.swml_user_event({
                            "type": "videos_available",
                            "data": {"videos": filtered_videos, "playing": filtered_videos[0]}
                        })
                else:
                    # No videos found
                    if video_type == "all":
                        response = f"Unfortunately, no videos are available for {content_name}."
                    else:
                        response = f"Unfortunately, no {video_type} is available for {content_name}."
                        
                        # Check if other types exist
                        if videos:
                            available_types = list(set([v["type"] for v in videos]))
                            if available_types:
                                response += f" However, I found: {', '.join(available_types).lower()}. "
                                response += "Would you like to see those instead?"
                    
                    result = SwaigFunctionResult(response=response)
                
                return result
                    
            except Exception as e:
                logger.error(f"Error getting videos: {e}")
                result = SwaigFunctionResult(
                    response="I couldn't fetch the videos. Please try again."
                )
                return result
        
        @self.tool(
            name="search_person",
            description="Search for actors, directors, or other film personalities",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The name of the person to search for (optional if person_id provided)"
                    },
                    "person_id": {
                        "type": "integer",
                        "description": "The TMDB ID of the person (use this from search results)"
                    },
                    "search_position": {
                        "type": "integer",
                        "description": "Position in search results (1-based index)"
                    }
                },
                "required": []
            }
        )
        def search_person(args, raw_data):
            query = args.get("query", "").strip()
            person_id = args.get("person_id")
            search_position = args.get("search_position")
            logger.info(f"search_person called with query='{query}', person_id={person_id}, search_position={search_position}")
            
            # Priority 1: Use person_id if provided
            if person_id:
                logger.info(f"Using provided person_id: {person_id}")
            
            # Priority 2: Use search position if provided
            elif search_position and self.person_search_mapping:
                if search_position in self.person_search_mapping:
                    person_info = self.person_search_mapping[search_position]
                    person_id = person_info["id"]
                    logger.info(f"Selected person at position {search_position}: '{person_info['name']}' (ID: {person_id})")
            
            try:
                if person_id:
                    details = self.tmdb.get_person_details(person_id)
                    self.current_person_id = person_id
                    
                    # Get total count and top films
                    total_movies = details.get("total_movie_count", 0)
                    films = details.get("filmography", [])
                    recent_films = films[:5]  # Top 5 most recent
                    known_for = [f["title"] for f in recent_films]
                    
                    # Log filmography IDs for AI reference
                    filmography_info = f"FILMOGRAPHY for {details['name']} with IDs:\n"
                    for i, film in enumerate(films[:20], 1):  # Show top 20 for AI
                        year = film.get('release_date', '')[:4] if film.get('release_date') else ''
                        filmography_info += f"  {i}. {film['title']} ({year}) -> movie_id={film['id']}\n"
                    logger.info(f"Person filmography: {filmography_info}")
                    
                    response = f"Here's {details['name']}, "
                    if details.get("known_for_department"):
                        response += f"known for {details['known_for_department'].lower()}. "
                    
                    if total_movies:
                        response += f"They've appeared in {total_movies} movies! "
                    
                    if known_for:
                        response += f"Recent films include: {', '.join(known_for)}. "
                    
                    if details.get("biography"):
                        bio_snippet = details["biography"][:150]
                        response += f"{bio_snippet}... "
                    
                    response += f"I'm showing all {total_movies} movies on your screen."
                    
                    result = SwaigFunctionResult(response=response)
                    
                    # Send event to frontend
                    result.swml_user_event({
                        "type": "person_details",
                        "data": details
                    })
                    
                    # Transition to person_details state
                    result.swml_change_step("person_details")
                    
                    return result
                    
                elif query:
                    results = self.tmdb.search_person(query)
                    
                    if results["results"]:
                        # If only one result, get details directly
                        if len(results["results"]) == 1:
                            person = results["results"][0]
                            details = self.tmdb.get_person_details(person["id"])
                            self.current_person_id = person["id"]
                            
                            total_movies = details.get("total_movie_count", 0)
                            
                            # Log filmography IDs for AI reference
                            films = details.get("filmography", [])
                            filmography_info = f"FILMOGRAPHY for {details['name']} with IDs:\n"
                            for i, film in enumerate(films[:20], 1):  # Show top 20 for AI
                                year = film.get('release_date', '')[:4] if film.get('release_date') else ''
                                filmography_info += f"  {i}. {film['title']} ({year}) -> movie_id={film['id']}\n"
                            logger.info(f"Person filmography: {filmography_info}")
                            
                            response = f"I found {details['name']}. "
                            if total_movies:
                                response += f"They've appeared in {total_movies} movies. "
                            response += f"I'm displaying their complete filmography on your screen."
                            
                            result = SwaigFunctionResult(response=response)
                            
                            # Send person details event
                            result.swml_user_event({
                                "type": "person_details",
                                "data": details
                            })
                            
                            # Transition to person_details state
                            result.swml_change_step("person_details")
                        else:
                            # Multiple results - let user choose
                            people = results["results"][:5]
                            person_descriptions = []
                            self.person_search_mapping = {}  # Reset mapping
                            
                            for i, p in enumerate(people, 1):
                                dept = p.get("known_for_department", "")
                                known_for = p.get("known_for", [])
                                known_for_titles = [item.get("title", item.get("name", "")) for item in known_for[:2]]
                                
                                # Include ID directly in the response text for LLM to see
                                desc = f"{i}. id: {p['id']} name: {p['name']} ({dept})"
                                if known_for_titles:
                                    desc += f" - Known for: {', '.join(known_for_titles)}"
                                person_descriptions.append(desc)
                                
                                # Store mapping for AI
                                self.person_search_mapping[i] = {
                                    "id": p["id"],
                                    "name": p["name"],
                                    "department": dept
                                }
                            
                            # Create info for AI about the person results with IDs
                            self.last_person_search_info = f"PERSON SEARCH RESULTS WITH IDS for '{query}':\n"
                            for pos, info in self.person_search_mapping.items():
                                self.last_person_search_info += f"  Position {pos}: {info['name']} ({info['department']}) -> person_id={info['id']}\n"
                            
                            logger.info(f"Person search mapping: {self.last_person_search_info}")
                            
                            response = f"I found several people matching '{query}':\n"
                            response += "\n".join(person_descriptions) + "\n"
                            response += "Which person would you like to know more about?"
                            
                            result = SwaigFunctionResult(response=response)
                            
                            # Send search results event
                            result.swml_user_event({
                                "type": "person_search_results",
                                "data": results
                            })
                    else:
                        response = f"I couldn't find anyone matching '{query}'."
                        result = SwaigFunctionResult(response=response)
                    
                    return result
                    
                else:
                    result = SwaigFunctionResult(
                        response="Please provide a name to search for."
                    )
                    return result
                    
            except Exception as e:
                logger.error(f"Error searching person: {e}")
                result = SwaigFunctionResult(
                    response="I couldn't search for that person. Please try again."
                )
                return result
        
        @self.tool(
            name="get_trending",
            description="Get trending movies for the day or week",
            parameters={
                "type": "object",
                "properties": {
                    "time_window": {
                        "type": "string",
                        "description": "The time window for trending movies (day or week)",
                        "enum": ["day", "week"]
                    }
                },
                "required": []
            }
        )
        def get_trending(args, raw_data):
            time_window = args.get("time_window", "week")
            logger.info(f"get_trending called with time_window: {time_window}")
            
            try:
                results = self.tmdb.get_trending(time_window=time_window)
                
                top_movies = results["results"][:24]
                movie_list = []
                self.search_result_mapping = {}  # Use same mapping as search
                
                for i, m in enumerate(top_movies, 1):
                    year = m.get('release_date', '')[:4] if m.get('release_date') else ''
                    movie_list.append(f"{i}. id: {m['id']} title: '{m['title']}' ({year})")
                    
                    # Store mapping for AI
                    self.search_result_mapping[i] = {
                        "id": m['id'],
                        "title": m['title'],
                        "year": year
                    }
                
                # Update last search info for AI
                self.last_search_info = f"TRENDING MOVIES WITH IDS:\n"
                for pos, info in self.search_result_mapping.items():
                    self.last_search_info += f"  Position {pos}: {info['title']} ({info['year']}) -> movie_id={info['id']}\n"
                
                logger.info(f"Trending mapping: {self.last_search_info}")
                
                response = f"Here are this {time_window}'s trending movies:\n"
                response += "\n".join(movie_list) + "\n"
                response += "They're all displayed on your screen. Which one interests you?"
                
                result = SwaigFunctionResult(response=response)
                
                # Send event to frontend (frontend will clear display when handling this)
                event_data = {
                    "type": "trending_movies",
                    "data": results
                }
                logger.info(f"Sending trending_movies event with {len(results['results'])} movies")
                result.swml_user_event(event_data)
                
                # Transition to browsing state
                result.swml_change_step("browsing")
                
                return result
                
            except Exception as e:
                logger.error(f"Error getting trending: {e}")
                return SwaigFunctionResult(
                    response="I couldn't fetch trending movies. Please try again."
                )
        
        @self.tool(
            name="get_movies_by_genre",
            description="Browse movies by genre like action, comedy, horror, or drama",
            parameters={
                "type": "object",
                "properties": {
                    "genre_name": {
                        "type": "string",
                        "description": "The genre name (e.g., action, comedy, horror, drama, sci-fi, romance)"
                    }
                },
                "required": ["genre_name"]
            }
        )
        def get_movies_by_genre(args, raw_data):
            genre_name = args.get("genre_name", "").lower()
            logger.info(f"get_movies_by_genre called with genre_name='{genre_name}'")
            
            if not genre_name:
                result = SwaigFunctionResult(
                    response="Please specify a genre like action, comedy, horror, or drama."
                )
                return result
            
            try:
                # Get genre mapping
                genres_data = self.tmdb.get_genres()
                genres = {g["name"].lower(): g["id"] for g in genres_data["genres"]}
                
                if genre_name not in genres:
                    available = ", ".join(list(genres.keys())[:24])
                    result = SwaigFunctionResult(
                        response=f"I don't recognize '{genre_name}'. "
                        f"Try genres like: {available}"
                    )
                    return result
                
                genre_id = genres[genre_name]
                results = self.tmdb.discover_by_genre([genre_id])
                
                top_movies = results["results"][:24]
                movie_list = []
                self.search_result_mapping = {}  # Use same mapping as search
                
                for i, m in enumerate(top_movies, 1):
                    year = m.get('release_date', '')[:4] if m.get('release_date') else ''
                    movie_list.append(f"{i}. id: {m['id']} title: '{m['title']}' ({year})")
                    
                    # Store mapping for AI
                    self.search_result_mapping[i] = {
                        "id": m['id'],
                        "title": m['title'],
                        "year": year
                    }
                
                # Update last search info for AI
                self.last_search_info = f"GENRE MOVIES WITH IDS for {genre_name}:\n"
                for pos, info in self.search_result_mapping.items():
                    self.last_search_info += f"  Position {pos}: {info['title']} ({info['year']}) -> movie_id={info['id']}\n"
                
                logger.info(f"Genre mapping: {self.last_search_info}")
                
                response = f"Here are popular {genre_name} movies:\n"
                response += "\n".join(movie_list) + "\n"
                response += "Which movie would you like to explore?"
                
                result = SwaigFunctionResult(response=response)
                
                # Send event to frontend
                result.swml_user_event({
                    "type": "genre_movies",
                    "data": {
                        "genre": genre_name.title(),
                        "movies": results["results"]
                    }
                })
                
                # Transition to browsing state
                result.swml_change_step("browsing")
                
                return result
                
            except Exception as e:
                logger.error(f"Error getting movies by genre: {e}")
                result = SwaigFunctionResult(
                    response="I couldn't fetch movies for that genre. Please try again."
                )
                return result
        
        @self.tool(name="add_to_watchlist", description="Add a movie to the user's watchlist")
        def add_to_watchlist(args, raw_data):
            movie_id = args.get("movie_id", self.current_movie_id)
            
            if not movie_id:
                result = SwaigFunctionResult(
                    response="Please select a movie to add to your watchlist."
                )
                return result
            
            try:
                # Check if already in watchlist
                if any(m["id"] == movie_id for m in self.watchlist):
                    result = SwaigFunctionResult(
                        response="This movie is already in your watchlist."
                    )
                    return result
                
                details = self.tmdb.get_movie_details(movie_id)
                
                # Add to watchlist
                self.watchlist.append({
                    "id": movie_id,
                    "title": details["title"],
                    "poster_path": details["poster_path"]
                })
                
                result = SwaigFunctionResult(
                    response=f"I've added '{details['title']}' to your watchlist. "
                    f"You now have {len(self.watchlist)} movies saved."
                )
                
                # Send event to frontend
                result.swml_user_event({
                    "type": "watchlist_updated",
                    "data": {"watchlist": self.watchlist}
                })
                
                return result
                
            except Exception as e:
                logger.error(f"Error adding to watchlist: {e}")
                result = SwaigFunctionResult(
                    response="I couldn't add that movie to your watchlist. Please try again."
                )
                return result
        
        @self.tool(
            name="clear_display",
            description="Clear the current display for a new search",
            parameters={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
        def clear_display(args, raw_data):
            # Reset state
            self.current_search_results = []
            self.current_movie_id = None
            self.current_person_id = None
            self.current_tv_id = None
            
            result = SwaigFunctionResult(
                response="I've cleared the display. What would you like to search for next?"
            )
            
            # Send event to frontend with background image
            result.swml_user_event({
                "type": "clear_display",
                "data": {
                    "background_image": "/background.png"
                }
            })
            
            # Transition to greeting state
            result.swml_change_step("greeting")
            
            return result
        
        @self.tool(
            name="search_tv",
            description="Search for TV shows by title",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The TV show title to search for"
                    }
                },
                "required": ["query"]
            }
        )
        def search_tv(args, raw_data):
            query = args.get("query", "").strip()
            logger.info(f"search_tv called with query: '{query}'")
            
            if not query:
                return SwaigFunctionResult(
                    response="Please provide a TV show title to search for."
                )
            
            try:
                results = self.tmdb.search_tv(query)
                logger.info(f"TMDB returned {len(results.get('results', []))} TV shows for '{query}'")
                self.current_search_results = results["results"]
                
                if results["results"]:
                    # Build TV show list and store mapping for AI
                    show_descriptions = []
                    self.search_result_mapping = {}  # Reset mapping
                    
                    for i, show in enumerate(results["results"], 1):
                        year = show.get('first_air_date', '')[:4] if show.get('first_air_date') else 'unknown year'
                        show_descriptions.append(f"{i}. id: {show['id']} title: '{show['name']}' ({year})")
                        
                        # Store mapping for AI to use internally
                        self.search_result_mapping[i] = {
                            "id": show['id'],
                            "name": show['name'],
                            "year": year,
                            "overview": show.get('overview', '')[:100]
                        }
                    
                    # Create info for AI about the search results with IDs
                    self.last_search_info = f"TV SHOW SEARCH RESULTS WITH IDS for '{query}':\n"
                    for pos, info in self.search_result_mapping.items():
                        self.last_search_info += f"  Position {pos}: {info['name']} ({info['year']}) -> tv_id={info['id']}\n"
                    
                    logger.info(f"TV search mapping: {self.last_search_info}")
                    
                    result = SwaigFunctionResult(
                        response=f"I found {len(results['results'])} TV shows matching '{query}'. "
                        f"Here are the results:\n{chr(10).join(show_descriptions)}\n"
                        f"Which show would you like to know more about?"
                    )
                else:
                    result = SwaigFunctionResult(
                        response=f"I couldn't find any TV shows matching '{query}'. "
                        f"Try searching with a different title or let me show you trending TV shows."
                    )
                
                # Send event to frontend
                logger.info(f"Sending tv_search_results event with {len(results['results'])} shows")
                result.swml_user_event({
                    "type": "tv_search_results",
                    "data": results
                })
                
                # Transition to browsing state
                result.swml_change_step("browsing")
                logger.info("Transitioned to browsing state")
                
                return result
            except Exception as e:
                logger.error(f"Error searching TV shows: {e}")
                return SwaigFunctionResult(
                    response="I encountered an error searching for TV shows. Please try again."
                )
        
        @self.tool(
            name="get_tv_details",
            description="Get detailed information about a specific TV show",
            parameters={
                "type": "object",
                "properties": {
                    "tv_title": {
                        "type": "string",
                        "description": "The title of the TV show (optional if tv_id provided)"
                    },
                    "tv_id": {
                        "type": "integer",
                        "description": "The TMDB ID of the TV show (preferred - use this from search results)"
                    },
                    "search_position": {
                        "type": "integer",
                        "description": "Position in search results (1-based index)"
                    }
                },
                "required": []
            }
        )
        def get_tv_details(args, raw_data):
            tv_id = args.get("tv_id")
            tv_title = args.get("tv_title")
            search_position = args.get("search_position")
            logger.info(f"get_tv_details called with tv_id={tv_id}, tv_title={tv_title}, search_position={search_position}")
            
            # Priority 1: Use tv_id if provided
            if tv_id:
                logger.info(f"Using provided tv_id: {tv_id}")
            
            # Priority 2: Use search position if provided
            elif search_position and self.search_result_mapping:
                if search_position in self.search_result_mapping:
                    show_info = self.search_result_mapping[search_position]
                    tv_id = show_info["id"]
                    tv_title = show_info.get("name", show_info.get("title"))
                    logger.info(f"Selected TV show at position {search_position}: '{tv_title}' (ID: {tv_id})")
                else:
                    logger.warning(f"Position {search_position} not found in search results")
            
            # Priority 3: Do a fresh search if we still don't have an ID
            if not tv_id and tv_title:
                logger.info(f"No tv_id provided, searching for '{tv_title}'")
                search_results = self.tmdb.search_tv(tv_title)
                
                if search_results["results"]:
                    tv_id = search_results["results"][0]["id"]
                    logger.info(f"Using first search result: ID {tv_id}")
            
            if not tv_id:
                result = SwaigFunctionResult(
                    response="Please specify which TV show you'd like details about."
                )
                return result
            
            try:
                details = self.tmdb.get_tv_details(tv_id)
                self.current_tv_id = tv_id
                
                # Build response
                genres = ", ".join(details["genres"][:3])
                seasons = details["number_of_seasons"]
                episodes = details["number_of_episodes"]
                
                response = f"Here's {details['name']}"
                if details['first_air_date']:
                    response += f" which premiered in {details['first_air_date'][:4]}"
                response += ". "
                
                if details["tagline"]:
                    response += f"\"{details['tagline']}\". "
                
                response += f"It's a {genres} series with {seasons} season{'s' if seasons != 1 else ''} "
                response += f"and {episodes} episodes. "
                
                if details["networks"]:
                    response += f"It airs on {', '.join(details['networks'][:2])}. "
                
                response += f"The show has a rating of {details['vote_average']:.1f} out of 10. "
                
                if details["overview"]:
                    response += f"Here's what it's about: {details['overview'][:200]}... "
                
                # Check if trailer is available before offering it
                has_trailer = False
                if details.get("videos"):
                    has_trailer = any(v["type"] == "Trailer" for v in details["videos"])
                
                # Build options based on available content
                options = []
                if has_trailer:
                    options.append("watch the trailer")
                options.append("ask about specific seasons")
                options.append("find similar shows")
                options.append("explore the cast members shown on screen")
                
                response += f"You can {', or '.join(options)}."
                
                result = SwaigFunctionResult(response=response)
                
                # Send event to frontend with all details
                event_data = {
                    "type": "tv_details",
                    "data": details
                }
                logger.info(f"Sending tv_details event for '{details['name']}' with {len(details.get('seasons', []))} seasons")
                logger.debug(f"Seasons data: {details.get('seasons', [])[:3]}")  # Log first 3 seasons for debugging
                result.swml_user_event(event_data)
                
                # Transition to tv_details state (we'll need to add this)
                result.swml_change_step("tv_details")
                logger.info("Transitioned to tv_details state")
                
                return result
                
            except Exception as e:
                logger.error(f"Error getting TV show details: {e}")
                result = SwaigFunctionResult(
                    response="I couldn't fetch the TV show details. Please try again."
                )
                return result
        
        @self.tool(
            name="get_season_details",
            description="Get details about a specific season of a TV show",
            parameters={
                "type": "object",
                "properties": {
                    "tv_id": {
                        "type": "integer",
                        "description": "The TMDB ID of the TV show (uses current if not provided)"
                    },
                    "season_number": {
                        "type": "integer",
                        "description": "The season number to get details for"
                    }
                },
                "required": ["season_number"]
            }
        )
        def get_season_details(args, raw_data):
            tv_id = args.get("tv_id", self.current_tv_id)
            season_number = args.get("season_number")
            
            if not tv_id:
                result = SwaigFunctionResult(
                    response="Please select a TV show first to see its seasons."
                )
                return result
            
            try:
                season = self.tmdb.get_tv_season(tv_id, season_number)
                
                episode_count = len(season["episodes"])
                
                response = f"Season {season_number}: {season['name']}. "
                response += f"This season has {episode_count} episodes. "
                
                if season["air_date"]:
                    response += f"It premiered on {season['air_date']}. "
                
                if season["overview"]:
                    response += f"{season['overview'][:150]}... "
                
                # List first few episodes
                if season["episodes"]:
                    response += "The first few episodes are: "
                    episode_list = []
                    for ep in season["episodes"][:3]:
                        episode_list.append(f"Episode {ep['episode_number']}: {ep['name']}")
                    response += ", ".join(episode_list) + ". "
                
                response += "I'm showing the full episode list on your screen."
                
                result = SwaigFunctionResult(response=response)
                
                # Send event to frontend
                result.swml_user_event({
                    "type": "season_details",
                    "data": season
                })
                
                return result
                
            except Exception as e:
                logger.error(f"Error getting season details: {e}")
                result = SwaigFunctionResult(
                    response="I couldn't fetch the season details. Please try again."
                )
                return result
        
        @self.tool(
            name="multi_search",
            description="Search for movies, TV shows, and people all at once",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query (can be movie, TV show, or person name)"
                    }
                },
                "required": ["query"]
            }
        )
        def multi_search(args, raw_data):
            query = args.get("query", "").strip()
            logger.info(f"multi_search called with query: '{query}'")
            
            if not query:
                return SwaigFunctionResult(
                    response="Please provide something to search for."
                )
            
            try:
                results = self.tmdb.multi_search(query)
                logger.info(f"Multi-search returned {len(results.get('results', []))} results")
                
                if results["results"]:
                    # Organize results by type
                    movies = []
                    tv_shows = []
                    people = []
                    self.search_result_mapping = {}
                    
                    position = 1
                    for item in results["results"]:
                        media_type = item.get("media_type")
                        
                        if media_type == "movie":
                            year = item.get('release_date', '')[:4] if item.get('release_date') else ''
                            movies.append(f"🎬 Movie: '{item['title']}' ({year})")
                            self.search_result_mapping[position] = {
                                "type": "movie",
                                "id": item['id'],
                                "title": item['title'],
                                "year": year
                            }
                        elif media_type == "tv":
                            year = item.get('first_air_date', '')[:4] if item.get('first_air_date') else ''
                            tv_shows.append(f"📺 TV: '{item['name']}' ({year})")
                            self.search_result_mapping[position] = {
                                "type": "tv",
                                "id": item['id'],
                                "name": item['name'],
                                "year": year
                            }
                        elif media_type == "person":
                            dept = item.get('known_for_department', '')
                            people.append(f"👤 Person: {item['name']} ({dept})")
                            self.search_result_mapping[position] = {
                                "type": "person",
                                "id": item['id'],
                                "name": item['name'],
                                "department": dept
                            }
                        position += 1
                    
                    # Build response
                    response = f"I found {len(results['results'])} results for '{query}':\n\n"
                    
                    all_results = []
                    pos = 1
                    
                    if movies:
                        for movie in movies:
                            all_results.append(f"{pos}. {movie}")
                            pos += 1
                    
                    if tv_shows:
                        for show in tv_shows:
                            all_results.append(f"{pos}. {show}")
                            pos += 1
                    
                    if people:
                        for person in people:
                            all_results.append(f"{pos}. {person}")
                            pos += 1
                    
                    response += "\n".join(all_results)
                    response += "\n\nWhich one would you like to know more about?"
                    
                    # Update last search info for AI
                    self.last_search_info = f"MULTI-SEARCH RESULTS WITH IDS for '{query}':\n"
                    for pos, info in self.search_result_mapping.items():
                        if info['type'] == 'movie':
                            self.last_search_info += f"  Position {pos}: Movie - {info['title']} ({info['year']}) -> movie_id={info['id']}\n"
                        elif info['type'] == 'tv':
                            self.last_search_info += f"  Position {pos}: TV - {info['name']} ({info['year']}) -> tv_id={info['id']}\n"
                        else:
                            self.last_search_info += f"  Position {pos}: Person - {info['name']} -> person_id={info['id']}\n"
                    
                    logger.info(f"Multi-search mapping: {self.last_search_info}")
                    
                    result = SwaigFunctionResult(response=response)
                else:
                    result = SwaigFunctionResult(
                        response=f"I couldn't find anything matching '{query}'. Try a different search term."
                    )
                
                # Send event to frontend
                result.swml_user_event({
                    "type": "multi_search_results",
                    "data": results
                })
                
                # Transition to browsing state
                result.swml_change_step("browsing")
                
                return result
            except Exception as e:
                logger.error(f"Error in multi-search: {e}")
                return SwaigFunctionResult(
                    response="I encountered an error searching. Please try again."
                )
        
        @self.tool(
            name="discover_content",
            description="Discover movies or TV shows with advanced filters",
            parameters={
                "type": "object",
                "properties": {
                    "content_type": {
                        "type": "string",
                        "description": "Type of content to discover",
                        "enum": ["movie", "tv"]
                    },
                    "year": {
                        "type": "integer",
                        "description": "Specific year of release"
                    },
                    "decade": {
                        "type": "string",
                        "description": "Decade (e.g., '1980s', '2000s')"
                    },
                    "genre": {
                        "type": "string",
                        "description": "Genre name (e.g., 'action', 'comedy', 'horror')"
                    },
                    "min_rating": {
                        "type": "number",
                        "description": "Minimum rating (0-10)"
                    },
                    "certification": {
                        "type": "string",
                        "description": "MPAA rating (G, PG, PG-13, R)"
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "Sort order",
                        "enum": ["popularity", "rating", "release_date", "title"]
                    }
                },
                "required": ["content_type"]
            }
        )
        def discover_content(args, raw_data):
            content_type = args.get("content_type", "movie")
            logger.info(f"discover_content called with type={content_type}, filters={args}")
            
            try:
                filters = {}
                
                # Process year/decade
                if "year" in args:
                    if content_type == "movie":
                        filters["year"] = args["year"]
                    else:
                        filters["first_air_year"] = args["year"]
                elif "decade" in args:
                    decade_str = args["decade"].replace("s", "")
                    decade = int(decade_str)
                    if content_type == "movie":
                        filters["year_gte"] = decade
                        filters["year_lte"] = decade + 9
                    else:
                        filters["air_date_gte"] = f"{decade}-01-01"
                        filters["air_date_lte"] = f"{decade + 9}-12-31"
                
                # Process genre
                if "genre" in args:
                    genre_name = args["genre"].lower()
                    if content_type == "movie":
                        genres_data = self.tmdb.get_genres()
                    else:
                        genres_data = self.tmdb.get_tv_genres()
                    
                    genres = {g["name"].lower(): g["id"] for g in genres_data["genres"]}
                    if genre_name in genres:
                        filters["genre_ids"] = [genres[genre_name]]
                
                # Process rating
                if "min_rating" in args:
                    filters["vote_average_gte"] = args["min_rating"]
                
                # Process certification
                if "certification" in args and content_type == "movie":
                    filters["certification"] = args["certification"]
                
                # Process sort
                sort_map = {
                    "popularity": "popularity.desc",
                    "rating": "vote_average.desc",
                    "release_date": "primary_release_date.desc" if content_type == "movie" else "first_air_date.desc",
                    "title": "original_title.asc" if content_type == "movie" else "name.asc"
                }
                filters["sort_by"] = sort_map.get(args.get("sort_by", "popularity"), "popularity.desc")
                
                # Call appropriate discover method
                if content_type == "movie":
                    results = self.tmdb.discover_movies_advanced(filters)
                else:
                    results = self.tmdb.discover_tv_advanced(filters)
                
                if results["results"]:
                    # Build response
                    item_list = []
                    self.search_result_mapping = {}
                    
                    for i, item in enumerate(results["results"][:15], 1):
                        if content_type == "movie":
                            year = item.get('release_date', '')[:4] if item.get('release_date') else ''
                            title = item['title']
                            item_list.append(f"{i}. '{title}' ({year}) - {item['vote_average']:.1f}⭐")
                            self.search_result_mapping[i] = {
                                "type": "movie",
                                "id": item['id'],
                                "title": title,
                                "year": year
                            }
                        else:
                            year = item.get('first_air_date', '')[:4] if item.get('first_air_date') else ''
                            name = item['name']
                            item_list.append(f"{i}. '{name}' ({year}) - {item['vote_average']:.1f}⭐")
                            self.search_result_mapping[i] = {
                                "type": "tv",
                                "id": item['id'],
                                "name": name,
                                "year": year
                            }
                    
                    # Build filter description
                    filter_desc = []
                    if "year" in args:
                        filter_desc.append(f"from {args['year']}")
                    elif "decade" in args:
                        filter_desc.append(f"from the {args['decade']}")
                    if "genre" in args:
                        filter_desc.append(args['genre'])
                    if "min_rating" in args:
                        filter_desc.append(f"rated {args['min_rating']}+")
                    if "certification" in args:
                        filter_desc.append(f"rated {args['certification']}")
                    
                    filter_str = " ".join(filter_desc) if filter_desc else "matching your criteria"
                    
                    response = f"I found {len(results['results'])} {'movies' if content_type == 'movie' else 'TV shows'} {filter_str}:\n\n"
                    response += "\n".join(item_list)
                    response += "\n\nWhich one would you like to explore?"
                    
                    result = SwaigFunctionResult(response=response)
                    
                    # Send event to frontend
                    result.swml_user_event({
                        "type": f"discover_{content_type}_results",
                        "data": results
                    })
                    
                    # Transition to browsing state
                    result.swml_change_step("browsing")
                else:
                    result = SwaigFunctionResult(
                        response=f"I couldn't find any {'movies' if content_type == 'movie' else 'TV shows'} matching those criteria. Try adjusting your filters."
                    )
                
                return result
                
            except Exception as e:
                logger.error(f"Error discovering content: {e}")
                return SwaigFunctionResult(
                    response="I encountered an error while searching. Please try again."
                )
        
        @self.tool(
            name="get_trending_tv",
            description="Get trending TV shows for the day or week",
            parameters={
                "type": "object",
                "properties": {
                    "time_window": {
                        "type": "string",
                        "description": "The time window for trending shows (day or week)",
                        "enum": ["day", "week"]
                    }
                },
                "required": []
            }
        )
        def get_trending_tv(args, raw_data):
            time_window = args.get("time_window", "week")
            logger.info(f"get_trending_tv called with time_window: {time_window}")
            
            try:
                results = self.tmdb.get_trending_tv(time_window=time_window)
                
                top_shows = results["results"][:24]
                show_list = []
                self.search_result_mapping = {}  # Use same mapping as search
                
                for i, show in enumerate(top_shows, 1):
                    year = show.get('first_air_date', '')[:4] if show.get('first_air_date') else ''
                    show_list.append(f"{i}. id: {show['id']} title: '{show['name']}' ({year})")
                    
                    # Store mapping for AI
                    self.search_result_mapping[i] = {
                        "id": show['id'],
                        "name": show['name'],
                        "year": year
                    }
                
                # Update last search info for AI
                self.last_search_info = f"TRENDING TV SHOWS WITH IDS:\n"
                for pos, info in self.search_result_mapping.items():
                    self.last_search_info += f"  Position {pos}: {info['name']} ({info['year']}) -> tv_id={info['id']}\n"
                
                logger.info(f"Trending TV mapping: {self.last_search_info}")
                
                response = f"Here are this {time_window}'s trending TV shows:\n"
                response += "\n".join(show_list) + "\n"
                response += "They're all displayed on your screen. Which one interests you?"
                
                result = SwaigFunctionResult(response=response)
                
                # Send event to frontend
                event_data = {
                    "type": "trending_tv",
                    "data": results
                }
                logger.info(f"Sending trending_tv event with {len(results['results'])} shows")
                result.swml_user_event(event_data)
                
                # Transition to browsing state
                result.swml_change_step("browsing")
                
                return result
                
            except Exception as e:
                logger.error(f"Error getting trending TV shows: {e}")
                return SwaigFunctionResult(
                    response="I couldn't fetch trending TV shows. Please try again."
                )
    
    async def _handle_root_request(self, request):
        """Handle root request and update video URLs dynamically"""
        # Get the host and protocol from request headers
        host = request.headers.get('host')
        protocol = request.headers.get('x-forwarded-proto', 'https')
        base_url = f"{protocol}://{host}"
        
        # Update video URLs with full paths
        self.set_param("video_idle_file", f"{base_url}/cinebot_idle.mp4")
        self.set_param("video_talking_file", f"{base_url}/cinebot_talking.mp4")
        
        # Set background image URL
        self.set_param("background_image", f"{base_url}/background.png")
        
        # Call the parent implementation
        response = await super()._handle_root_request(request)
        
        # Add initial background display event
        if hasattr(response, 'body'):
            import json
            try:
                body = json.loads(response.body)
                # Add initial user event to show background
                if 'sections' not in body:
                    body['sections'] = []
                body['sections'].append({
                    "type": "user_event",
                    "event": {
                        "type": "initial_display",
                        "data": {
                            "background_image": f"{base_url}/background.png"
                        }
                    }
                })
                response.body = json.dumps(body)
            except:
                pass
        
        return response
    
    def get_app(self):
        """Create FastAPI app with SWML router and static files"""
        app = FastAPI(title="CineBot Movie Assistant")
        
        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # API endpoints
        @app.get("/api/menu")
        async def get_menu():
            """Return available genres for the UI"""
            try:
                genres = self.tmdb.get_genres()
                return JSONResponse(content=genres)
            except:
                return JSONResponse(content={"genres": []})
        
        @app.get("/api/watchlist")
        async def get_watchlist():
            """Return current watchlist"""
            return JSONResponse(content={"watchlist": self.watchlist})
        
        # Create router for SWML endpoints
        router = self.as_router()
        
        # Mount the SWML router at /swml
        app.include_router(router, prefix=self.route)
        
        # Add explicit handler for /swml (without trailing slash) since SignalWire posts here
        @app.post("/swml")
        async def handle_swml(request: Request, response: Response):
            """Handle POST to /swml - SignalWire's webhook endpoint"""
            return await self._handle_root_request(request)
        
        # Optionally also handle GET for testing
        @app.get("/swml")
        async def handle_swml_get(request: Request, response: Response):
            """Handle GET to /swml for testing"""
            return await self._handle_root_request(request)
        
        # Serve static files (HTML, JS, CSS, videos)
        app.mount("/", StaticFiles(directory="web", html=True), name="static")
        
        return app


def main():
    agent = MovieAgent()
    app = agent.get_app()
    
    # Get auth credentials for display
    username, password = agent.get_basic_auth_credentials()
    
    import uvicorn
    port = int(os.getenv("PORT", 3030))
    host = os.getenv("HOST", "0.0.0.0")
    
    print("=" * 60)
    print("CineBot Movie Assistant")
    print("=" * 60)
    print(f"\nServer: http://{host}:{port}")
    print(f"Basic Auth: {username}:{password}")
    print("\nEndpoints:")
    print(f"  Web UI:     http://{host}:{port}/")
    print(f"  SWML:       http://{host}:{port}/swml")
    print("=" * 60)
    
    uvicorn.run(
        app,
        host=host,
        port=port
    )


if __name__ == "__main__":
    main()
