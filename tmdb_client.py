import tmdbsimple as tmdb
import os
from typing import Optional, List, Dict, Any
import json
import redis
from datetime import datetime, timedelta
import hashlib


class TMDBClient:
    def __init__(self, api_key: str, redis_url: Optional[str] = None):
        self.api_key = api_key
        tmdb.API_KEY = api_key
        self.base_url = "https://api.themoviedb.org/3"
        self.image_base = "https://image.tmdb.org/t/p/"
        
        self.redis_client = None
        if redis_url:
            try:
                self.redis_client = redis.from_url(redis_url)
                self.redis_client.ping()
                print("Redis caching enabled")
            except Exception as e:
                print(f"Redis connection failed: {e}. Continuing without cache.")
                self.redis_client = None
    
    def _get_cache_key(self, method: str, **kwargs) -> str:
        key_data = f"{method}:{json.dumps(kwargs, sort_keys=True)}"
        return f"tmdb:{hashlib.md5(key_data.encode()).hexdigest()}"
    
    def _get_cached(self, cache_key: str) -> Optional[Dict]:
        if not self.redis_client:
            return None
        try:
            cached = self.redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass
        return None
    
    def _set_cache(self, cache_key: str, data: Dict, ttl: int = 86400):
        if not self.redis_client:
            return
        try:
            self.redis_client.setex(
                cache_key,
                ttl,
                json.dumps(data)
            )
        except Exception:
            pass
    
    def get_poster_url(self, path: str, size: str = "w500") -> str:
        if not path:
            return ""  # Return empty string, let CSS handle placeholder
        return f"{self.image_base}{size}{path}"
    
    def get_profile_url(self, path: str, size: str = "w185") -> str:
        if not path:
            return ""  # Return empty string, let CSS handle placeholder
        return f"{self.image_base}{size}{path}"
    
    def search_movie(self, query: str, page: int = 1, language: str = "en-US") -> Dict[str, Any]:
        cache_key = self._get_cache_key("search_movie", query=query, page=page, language=language)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        search = tmdb.Search()
        response = search.movie(query=query, page=page, language=language)
        
        # Log the search for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"TMDB search for '{query}' returned {len(search.results)} results")
        
        results = {
            "results": [
                {
                    "id": movie["id"],
                    "title": movie["title"],
                    "release_date": movie.get("release_date", ""),
                    "overview": movie.get("overview", ""),
                    "poster_path": self.get_poster_url(movie.get("poster_path", "")),
                    "vote_average": movie.get("vote_average", 0),
                    "popularity": movie.get("popularity", 0)
                }
                for movie in search.results[:10]  # Increased from 5 to 10
            ],
            "total_results": search.total_results
        }
        
        self._set_cache(cache_key, results)
        return results
    
    def get_movie_details(self, movie_id: int, language: str = "en-US") -> Dict[str, Any]:
        cache_key = self._get_cache_key("movie_details", movie_id=movie_id, language=language)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        movie = tmdb.Movies(movie_id)
        info = movie.info(append_to_response="credits,videos,similar,images,release_dates", language=language)
        
        details = {
            "id": info["id"],
            "title": info["title"],
            "tagline": info.get("tagline", ""),
            "overview": info.get("overview", ""),
            "release_date": info.get("release_date", ""),
            "runtime": info.get("runtime", 0),
            "genres": [g["name"] for g in info.get("genres", [])],
            "vote_average": info.get("vote_average", 0),
            "vote_count": info.get("vote_count", 0),
            "budget": info.get("budget", 0),
            "revenue": info.get("revenue", 0),
            "poster_path": self.get_poster_url(info.get("poster_path", "")),
            "backdrop_path": self.get_poster_url(info.get("backdrop_path", ""), "w1280"),
            "homepage": info.get("homepage", ""),
            "imdb_id": info.get("imdb_id", ""),
            "status": info.get("status", ""),
            "production_companies": [
                c["name"] for c in info.get("production_companies", [])[:3]
            ]
        }
        
        # Get content rating (MPAA rating for US)
        if "release_dates" in info:
            for country in info["release_dates"].get("results", []):
                if country["iso_3166_1"] == "US":
                    for release in country.get("release_dates", []):
                        if release.get("certification"):
                            details["content_rating"] = release["certification"]
                            break
                    break
        
        if "content_rating" not in details:
            details["content_rating"] = "NR"  # Not Rated
        
        if "credits" in info:
            details["cast"] = [
                {
                    "id": person["id"],
                    "name": person["name"],
                    "character": person.get("character", ""),
                    "profile_path": self.get_profile_url(person.get("profile_path", "")),
                    "order": person.get("order", 999)
                }
                for person in info["credits"].get("cast", [])[:10]
            ]
            
            details["crew"] = [
                {
                    "id": person["id"],
                    "name": person["name"],
                    "job": person["job"],
                    "department": person["department"],
                    "profile_path": self.get_profile_url(person.get("profile_path", ""))
                }
                for person in info["credits"].get("crew", [])
                if person["job"] in ["Director", "Producer", "Screenplay", "Writer"]
            ][:5]
        
        if "videos" in info:
            details["videos"] = [
                {
                    "key": video["key"],
                    "name": video["name"],
                    "type": video["type"],
                    "site": video["site"],
                    "size": video.get("size", 720),  # Video quality: 360, 480, 720, 1080
                    "official": video.get("official", False),
                    "published_at": video.get("published_at", "")
                }
                for video in info["videos"].get("results", [])
                if video["site"] == "YouTube"
            ][:3]
        
        if "similar" in info:
            details["similar"] = [
                {
                    "id": movie["id"],
                    "title": movie["title"],
                    "poster_path": self.get_poster_url(movie.get("poster_path", "")),
                    "vote_average": movie.get("vote_average", 0)
                }
                for movie in info["similar"].get("results", [])[:6]
            ]
        
        self._set_cache(cache_key, details)
        return details
    
    def search_person(self, query: str, language: str = "en-US") -> Dict[str, Any]:
        cache_key = self._get_cache_key("search_person", query=query, language=language)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        search = tmdb.Search()
        response = search.person(query=query, language=language)
        
        results = {
            "results": [
                {
                    "id": person["id"],
                    "name": person["name"],
                    "known_for_department": person.get("known_for_department", ""),
                    "profile_path": self.get_profile_url(person.get("profile_path", "")),
                    "popularity": person.get("popularity", 0),
                    "known_for": [
                        {
                            "id": item.get("id"),
                            "title": item.get("title", item.get("name", "")),
                            "media_type": item.get("media_type", "")
                        }
                        for item in person.get("known_for", [])[:3]
                    ]
                }
                for person in search.results[:5]
            ]
        }
        
        self._set_cache(cache_key, results, ttl=43200)
        return results
    
    def get_person_details(self, person_id: int, language: str = "en-US") -> Dict[str, Any]:
        cache_key = self._get_cache_key("person_details", person_id=person_id, language=language)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        person = tmdb.People(person_id)
        info = person.info(append_to_response="movie_credits,images", language=language)
        
        details = {
            "id": info["id"],
            "name": info["name"],
            "biography": info.get("biography", ""),
            "birthday": info.get("birthday", ""),
            "deathday": info.get("deathday", ""),
            "place_of_birth": info.get("place_of_birth", ""),
            "profile_path": self.get_profile_url(info.get("profile_path", "")),
            "known_for_department": info.get("known_for_department", ""),
            "popularity": info.get("popularity", 0)
        }
        
        if "movie_credits" in info:
            # Get all movies, not just 10
            all_movies = info["movie_credits"].get("cast", []) + info["movie_credits"].get("crew", [])
            
            # Remove duplicates (person might be both cast and crew)
            seen_ids = set()
            unique_movies = []
            for movie in all_movies:
                if movie["id"] not in seen_ids:
                    seen_ids.add(movie["id"])
                    unique_movies.append(movie)
            
            details["filmography"] = [
                {
                    "id": movie["id"],
                    "title": movie["title"],
                    "character": movie.get("character", movie.get("job", "")),
                    "release_date": movie.get("release_date", ""),
                    "poster_path": self.get_poster_url(movie.get("poster_path", "")),
                    "vote_average": movie.get("vote_average", 0)
                }
                for movie in sorted(
                    unique_movies,
                    key=lambda x: x.get("release_date", "") or "0000",
                    reverse=True
                )
            ]
            
            # Also provide a count
            details["total_movie_count"] = len(details["filmography"])
        
        self._set_cache(cache_key, details)
        return details
    
    def get_trending(self, media_type: str = "movie", time_window: str = "week", language: str = "en-US") -> Dict[str, Any]:
        cache_key = self._get_cache_key("trending", media_type=media_type, time_window=time_window, language=language)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        trending = tmdb.Trending(media_type=media_type, time_window=time_window)
        info = trending.info(language=language)
        
        results = {
            "results": [
                {
                    "id": item["id"],
                    "title": item.get("title", item.get("name", "")),
                    "overview": item.get("overview", ""),
                    "poster_path": self.get_poster_url(item.get("poster_path", "")),
                    "vote_average": item.get("vote_average", 0),
                    "release_date": item.get("release_date", item.get("first_air_date", ""))
                }
                for item in info["results"][:10]
            ]
        }
        
        self._set_cache(cache_key, results, ttl=3600)
        return results
    
    def discover_by_genre(self, genre_ids: List[int], page: int = 1, language: str = "en-US") -> Dict[str, Any]:
        cache_key = self._get_cache_key("discover_genre", genre_ids=genre_ids, page=page, language=language)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        discover = tmdb.Discover()
        response = discover.movie(
            with_genres=",".join(map(str, genre_ids)),
            page=page,
            sort_by="popularity.desc",
            language=language
        )
        
        results = {
            "results": [
                {
                    "id": movie["id"],
                    "title": movie["title"],
                    "overview": movie.get("overview", ""),
                    "poster_path": self.get_poster_url(movie.get("poster_path", "")),
                    "vote_average": movie.get("vote_average", 0),
                    "release_date": movie.get("release_date", "")
                }
                for movie in discover.results[:10]
            ]
        }
        
        self._set_cache(cache_key, results)
        return results
    
    def get_genres(self) -> Dict[str, Any]:
        cache_key = self._get_cache_key("genres")
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        genres = tmdb.Genres()
        movie_genres = genres.movie_list()
        
        results = {
            "genres": movie_genres["genres"]
        }
        
        self._set_cache(cache_key, results, ttl=604800)
        return results
    
    def get_watch_providers(self, movie_id: int, country: str = "US") -> Dict[str, Any]:
        """Get watch provider information for a movie"""
        cache_key = self._get_cache_key("watch_providers", movie_id=movie_id, country=country)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        try:
            movie = tmdb.Movies(movie_id)
            providers = movie.watch_providers()
            
            country_data = providers.get("results", {}).get(country, {})
            
            results = {
                "country": country,
                "link": country_data.get("link", ""),
                "providers": []
            }
            
            # Combine all provider types
            provider_types = ["flatrate", "rent", "buy", "free"]
            seen_providers = set()
            
            for provider_type in provider_types:
                if provider_type in country_data:
                    for provider in country_data[provider_type]:
                        if provider["provider_id"] not in seen_providers:
                            results["providers"].append({
                                "provider_id": provider["provider_id"],
                                "provider_name": provider["provider_name"],
                                "logo_path": f"https://image.tmdb.org/t/p/original{provider['logo_path']}" if provider.get("logo_path") else None,
                                "display_priority": provider.get("display_priority", 999),
                                "type": provider_type
                            })
                            seen_providers.add(provider["provider_id"])
            
            # Sort by display priority
            results["providers"].sort(key=lambda x: x["display_priority"])
            
            self._set_cache(cache_key, results, ttl=86400)
            return results
            
        except Exception as e:
            print(f"Error fetching watch providers: {e}")
            return {"country": country, "providers": [], "link": ""}
    
    def search_tv(self, query: str, page: int = 1, language: str = "en-US") -> Dict[str, Any]:
        """Search for TV shows"""
        cache_key = self._get_cache_key("search_tv", query=query, page=page, language=language)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        search = tmdb.Search()
        response = search.tv(query=query, page=page, language=language)
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"TMDB TV search for '{query}' returned {len(search.results)} results")
        
        results = {
            "results": [
                {
                    "id": show["id"],
                    "name": show["name"],
                    "first_air_date": show.get("first_air_date", ""),
                    "overview": show.get("overview", ""),
                    "poster_path": self.get_poster_url(show.get("poster_path", "")),
                    "vote_average": show.get("vote_average", 0),
                    "popularity": show.get("popularity", 0)
                }
                for show in search.results[:10]
            ],
            "total_results": search.total_results
        }
        
        self._set_cache(cache_key, results)
        return results
    
    def get_tv_details(self, tv_id: int, language: str = "en-US") -> Dict[str, Any]:
        """Get detailed information about a TV show"""
        cache_key = self._get_cache_key("tv_details", tv_id=tv_id, language=language)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        tv = tmdb.TV(tv_id)
        info = tv.info(append_to_response="credits,videos,similar,content_ratings,watch/providers", language=language)
        
        details = {
            "id": info["id"],
            "name": info["name"],
            "tagline": info.get("tagline", ""),
            "overview": info.get("overview", ""),
            "first_air_date": info.get("first_air_date", ""),
            "last_air_date": info.get("last_air_date", ""),
            "episode_run_time": info.get("episode_run_time", []),
            "genres": [g["name"] for g in info.get("genres", [])],
            "vote_average": info.get("vote_average", 0),
            "vote_count": info.get("vote_count", 0),
            "poster_path": self.get_poster_url(info.get("poster_path", "")),
            "backdrop_path": self.get_poster_url(info.get("backdrop_path", ""), "w1280"),
            "homepage": info.get("homepage", ""),
            "status": info.get("status", ""),
            "type": info.get("type", ""),
            "number_of_episodes": info.get("number_of_episodes", 0),
            "number_of_seasons": info.get("number_of_seasons", 0),
            "networks": [n["name"] for n in info.get("networks", [])],
            "created_by": [c["name"] for c in info.get("created_by", [])],
            "production_companies": [c["name"] for c in info.get("production_companies", [])[:3]],
            "seasons": []
        }
        
        # Get content rating
        if "content_ratings" in info:
            for rating in info["content_ratings"].get("results", []):
                if rating["iso_3166_1"] == "US":
                    details["content_rating"] = rating.get("rating", "NR")
                    break
        
        if "content_rating" not in details:
            details["content_rating"] = "NR"
        
        # Process seasons
        for season in info.get("seasons", []):
            if season.get("season_number", 0) >= 0:  # Include season 0 (specials)
                details["seasons"].append({
                    "id": season["id"],
                    "name": season["name"],
                    "season_number": season["season_number"],
                    "episode_count": season["episode_count"],
                    "air_date": season.get("air_date", ""),
                    "overview": season.get("overview", ""),
                    "poster_path": self.get_poster_url(season.get("poster_path", ""))
                })
        
        # Sort seasons by number
        details["seasons"].sort(key=lambda x: x["season_number"])
        
        # Get cast and crew
        if "credits" in info:
            details["cast"] = [
                {
                    "id": person["id"],
                    "name": person["name"],
                    "character": person.get("character", ""),
                    "profile_path": self.get_profile_url(person.get("profile_path", "")),
                    "order": person.get("order", 999)
                }
                for person in info["credits"].get("cast", [])[:10]
            ]
            
            details["crew"] = [
                {
                    "id": person["id"],
                    "name": person["name"],
                    "job": person["job"],
                    "department": person["department"],
                    "profile_path": self.get_profile_url(person.get("profile_path", ""))
                }
                for person in info["credits"].get("crew", [])
                if person["job"] in ["Executive Producer", "Producer", "Creator"]
            ][:5]
        
        # Get videos
        if "videos" in info:
            details["videos"] = [
                {
                    "key": video["key"],
                    "name": video["name"],
                    "type": video["type"],
                    "site": video["site"],
                    "size": video.get("size", 720),  # Video quality: 360, 480, 720, 1080
                    "official": video.get("official", False),
                    "published_at": video.get("published_at", "")
                }
                for video in info["videos"].get("results", [])
                if video["site"] == "YouTube"
            ][:3]
        
        # Get similar shows
        if "similar" in info:
            details["similar"] = [
                {
                    "id": show["id"],
                    "name": show["name"],
                    "poster_path": self.get_poster_url(show.get("poster_path", "")),
                    "vote_average": show.get("vote_average", 0)
                }
                for show in info["similar"].get("results", [])[:6]
            ]
        
        # Get watch providers
        if "watch/providers" in info:
            country_data = info["watch/providers"].get("results", {}).get("US", {})
            details["watch_providers"] = {
                "country": "US",
                "link": country_data.get("link", ""),
                "providers": []
            }
            
            provider_types = ["flatrate", "rent", "buy", "free"]
            seen_providers = set()
            
            for provider_type in provider_types:
                if provider_type in country_data:
                    for provider in country_data[provider_type]:
                        if provider["provider_id"] not in seen_providers:
                            details["watch_providers"]["providers"].append({
                                "provider_id": provider["provider_id"],
                                "provider_name": provider["provider_name"],
                                "logo_path": f"https://image.tmdb.org/t/p/original{provider['logo_path']}" if provider.get("logo_path") else None,
                                "display_priority": provider.get("display_priority", 999),
                                "type": provider_type
                            })
                            seen_providers.add(provider["provider_id"])
            
            details["watch_providers"]["providers"].sort(key=lambda x: x["display_priority"])
        
        self._set_cache(cache_key, details)
        return details
    
    def get_tv_season(self, tv_id: int, season_number: int, language: str = "en-US") -> Dict[str, Any]:
        """Get detailed information about a TV season"""
        cache_key = self._get_cache_key("tv_season", tv_id=tv_id, season_number=season_number, language=language)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        tv_season = tmdb.TV_Seasons(tv_id, season_number)
        info = tv_season.info(language=language)
        
        details = {
            "id": info["id"],
            "name": info["name"],
            "season_number": info["season_number"],
            "air_date": info.get("air_date", ""),
            "overview": info.get("overview", ""),
            "poster_path": self.get_poster_url(info.get("poster_path", "")),
            "episodes": []
        }
        
        # Process episodes
        for episode in info.get("episodes", []):
            details["episodes"].append({
                "id": episode["id"],
                "name": episode["name"],
                "episode_number": episode["episode_number"],
                "air_date": episode.get("air_date", ""),
                "overview": episode.get("overview", ""),
                "runtime": episode.get("runtime", 0),
                "still_path": self.get_poster_url(episode.get("still_path", ""), "w500"),
                "vote_average": episode.get("vote_average", 0),
                "guest_stars": [
                    {
                        "name": star["name"],
                        "character": star.get("character", ""),
                        "profile_path": self.get_profile_url(star.get("profile_path", ""))
                    }
                    for star in episode.get("guest_stars", [])[:3]
                ]
            })
        
        self._set_cache(cache_key, details)
        return details
    
    def get_tv_episode(self, tv_id: int, season_number: int, episode_number: int, language: str = "en-US") -> Dict[str, Any]:
        """Get detailed information about a TV episode"""
        cache_key = self._get_cache_key("tv_episode", tv_id=tv_id, season_number=season_number, episode_number=episode_number, language=language)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        tv_episode = tmdb.TV_Episodes(tv_id, season_number, episode_number)
        info = tv_episode.info(append_to_response="credits,videos", language=language)
        
        details = {
            "id": info["id"],
            "name": info["name"],
            "episode_number": info["episode_number"],
            "season_number": info["season_number"],
            "air_date": info.get("air_date", ""),
            "overview": info.get("overview", ""),
            "runtime": info.get("runtime", 0),
            "still_path": self.get_poster_url(info.get("still_path", ""), "w500"),
            "vote_average": info.get("vote_average", 0),
            "vote_count": info.get("vote_count", 0)
        }
        
        # Get cast and crew
        if "credits" in info:
            details["guest_stars"] = [
                {
                    "id": person["id"],
                    "name": person["name"],
                    "character": person.get("character", ""),
                    "profile_path": self.get_profile_url(person.get("profile_path", ""))
                }
                for person in info["credits"].get("guest_stars", [])[:5]
            ]
            
            details["crew"] = [
                {
                    "id": person["id"],
                    "name": person["name"],
                    "job": person["job"],
                    "department": person["department"]
                }
                for person in info["credits"].get("crew", [])
                if person["job"] in ["Director", "Writer"]
            ]
        
        # Get videos
        if "videos" in info:
            details["videos"] = [
                {
                    "key": video["key"],
                    "name": video["name"],
                    "type": video["type"],
                    "site": video["site"]
                }
                for video in info["videos"].get("results", [])
                if video["site"] == "YouTube"
            ]
        
        self._set_cache(cache_key, details)
        return details
    
    def get_trending_tv(self, time_window: str = "week", language: str = "en-US") -> Dict[str, Any]:
        """Get trending TV shows"""
        cache_key = self._get_cache_key("trending_tv", time_window=time_window, language=language)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        trending = tmdb.Trending(media_type="tv", time_window=time_window)
        info = trending.info(language=language)
        
        results = {
            "results": [
                {
                    "id": item["id"],
                    "name": item.get("name", ""),
                    "overview": item.get("overview", ""),
                    "poster_path": self.get_poster_url(item.get("poster_path", "")),
                    "vote_average": item.get("vote_average", 0),
                    "first_air_date": item.get("first_air_date", "")
                }
                for item in info["results"][:10]
            ]
        }
        
        self._set_cache(cache_key, results, ttl=3600)
        return results
    
    def multi_search(self, query: str, page: int = 1, language: str = "en-US") -> Dict[str, Any]:
        """Search for movies, TV shows, and people all at once"""
        cache_key = self._get_cache_key("multi_search", query=query, page=page, language=language)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        search = tmdb.Search()
        response = search.multi(query=query, page=page, language=language)
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"TMDB multi-search for '{query}' returned {len(search.results)} results")
        
        results = {
            "results": [],
            "total_results": search.total_results
        }
        
        for item in search.results[:15]:  # Get more results for multi-search
            media_type = item.get("media_type")
            
            if media_type == "movie":
                results["results"].append({
                    "media_type": "movie",
                    "id": item["id"],
                    "title": item["title"],
                    "release_date": item.get("release_date", ""),
                    "overview": item.get("overview", ""),
                    "poster_path": self.get_poster_url(item.get("poster_path", "")),
                    "vote_average": item.get("vote_average", 0),
                    "popularity": item.get("popularity", 0)
                })
            elif media_type == "tv":
                results["results"].append({
                    "media_type": "tv",
                    "id": item["id"],
                    "name": item["name"],
                    "first_air_date": item.get("first_air_date", ""),
                    "overview": item.get("overview", ""),
                    "poster_path": self.get_poster_url(item.get("poster_path", "")),
                    "vote_average": item.get("vote_average", 0),
                    "popularity": item.get("popularity", 0)
                })
            elif media_type == "person":
                results["results"].append({
                    "media_type": "person",
                    "id": item["id"],
                    "name": item["name"],
                    "known_for_department": item.get("known_for_department", ""),
                    "profile_path": self.get_profile_url(item.get("profile_path", "")),
                    "popularity": item.get("popularity", 0),
                    "known_for": [
                        {
                            "id": kf.get("id"),
                            "title": kf.get("title", kf.get("name", "")),
                            "media_type": kf.get("media_type", "")
                        }
                        for kf in item.get("known_for", [])[:2]
                    ]
                })
        
        self._set_cache(cache_key, results)
        return results
    
    def discover_movies_advanced(self, filters: Dict[str, Any], page: int = 1, language: str = "en-US") -> Dict[str, Any]:
        """Discover movies with advanced filters"""
        cache_key = self._get_cache_key("discover_movies_advanced", filters=filters, page=page, language=language)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        discover = tmdb.Discover()
        
        # Build parameters from filters
        params = {
            "page": page,
            "language": language,
            "sort_by": filters.get("sort_by", "popularity.desc")
        }
        
        # Add optional filters
        if "year" in filters:
            params["primary_release_year"] = filters["year"]
        if "year_gte" in filters:
            params["primary_release_date.gte"] = f"{filters['year_gte']}-01-01"
        if "year_lte" in filters:
            params["primary_release_date.lte"] = f"{filters['year_lte']}-12-31"
        if "genre_ids" in filters:
            params["with_genres"] = ",".join(map(str, filters["genre_ids"]))
        if "vote_average_gte" in filters:
            params["vote_average.gte"] = filters["vote_average_gte"]
        if "runtime_gte" in filters:
            params["with_runtime.gte"] = filters["runtime_gte"]
        if "runtime_lte" in filters:
            params["with_runtime.lte"] = filters["runtime_lte"]
        if "with_cast" in filters:
            params["with_cast"] = filters["with_cast"]
        if "with_crew" in filters:
            params["with_crew"] = filters["with_crew"]
        if "with_companies" in filters:
            params["with_companies"] = filters["with_companies"]
        if "with_keywords" in filters:
            params["with_keywords"] = filters["with_keywords"]
        if "certification" in filters:
            params["certification_country"] = "US"
            params["certification"] = filters["certification"]
        if "with_original_language" in filters:
            params["with_original_language"] = filters["with_original_language"]
        
        response = discover.movie(**params)
        
        results = {
            "results": [
                {
                    "id": movie["id"],
                    "title": movie["title"],
                    "release_date": movie.get("release_date", ""),
                    "overview": movie.get("overview", ""),
                    "poster_path": self.get_poster_url(movie.get("poster_path", "")),
                    "vote_average": movie.get("vote_average", 0),
                    "popularity": movie.get("popularity", 0)
                }
                for movie in discover.results[:20]
            ],
            "total_results": discover.total_results,
            "filters_applied": filters
        }
        
        self._set_cache(cache_key, results)
        return results
    
    def discover_tv_advanced(self, filters: Dict[str, Any], page: int = 1, language: str = "en-US") -> Dict[str, Any]:
        """Discover TV shows with advanced filters"""
        cache_key = self._get_cache_key("discover_tv_advanced", filters=filters, page=page, language=language)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        discover = tmdb.Discover()
        
        # Build parameters from filters
        params = {
            "page": page,
            "language": language,
            "sort_by": filters.get("sort_by", "popularity.desc")
        }
        
        # Add optional filters
        if "first_air_year" in filters:
            params["first_air_date_year"] = filters["first_air_year"]
        if "air_date_gte" in filters:
            params["air_date.gte"] = filters["air_date_gte"]
        if "air_date_lte" in filters:
            params["air_date.lte"] = filters["air_date_lte"]
        if "genre_ids" in filters:
            params["with_genres"] = ",".join(map(str, filters["genre_ids"]))
        if "vote_average_gte" in filters:
            params["vote_average.gte"] = filters["vote_average_gte"]
        if "with_networks" in filters:
            params["with_networks"] = filters["with_networks"]
        if "with_companies" in filters:
            params["with_companies"] = filters["with_companies"]
        if "with_keywords" in filters:
            params["with_keywords"] = filters["with_keywords"]
        if "with_original_language" in filters:
            params["with_original_language"] = filters["with_original_language"]
        if "with_status" in filters:
            params["with_status"] = filters["with_status"]
        if "with_type" in filters:
            params["with_type"] = filters["with_type"]
        
        response = discover.tv(**params)
        
        results = {
            "results": [
                {
                    "id": show["id"],
                    "name": show["name"],
                    "first_air_date": show.get("first_air_date", ""),
                    "overview": show.get("overview", ""),
                    "poster_path": self.get_poster_url(show.get("poster_path", "")),
                    "vote_average": show.get("vote_average", 0),
                    "popularity": show.get("popularity", 0)
                }
                for show in discover.results[:20]
            ],
            "total_results": discover.total_results,
            "filters_applied": filters
        }
        
        self._set_cache(cache_key, results)
        return results
    
    def get_tv_genres(self) -> Dict[str, Any]:
        """Get list of TV genres"""
        cache_key = self._get_cache_key("tv_genres")
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        genres = tmdb.Genres()
        tv_genres = genres.tv_list()
        
        results = {
            "genres": tv_genres["genres"]
        }
        
        self._set_cache(cache_key, results, ttl=604800)
        return results
    
    def get_movie_keywords(self, query: str) -> Dict[str, Any]:
        """Search for movie keywords"""
        cache_key = self._get_cache_key("keywords", query=query)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        search = tmdb.Search()
        response = search.keyword(query=query)
        
        results = {
            "keywords": search.results[:10]
        }
        
        self._set_cache(cache_key, results, ttl=86400)
        return results
    
    # ============= NEW ENHANCED METHODS =============
    
    def get_alternative_titles(self, content_id: int, content_type: str = "movie") -> Dict[str, Any]:
        """Get alternative titles for a movie or TV show"""
        cache_key = self._get_cache_key(f"{content_type}_alt_titles", content_id=content_id)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        if content_type == "movie":
            movie = tmdb.Movie(content_id)
            titles = movie.alternative_titles()
        else:
            tv = tmdb.TV(content_id)
            titles = tv.alternative_titles()
        
        results = {
            "id": content_id,
            "titles": titles.get("titles", titles.get("results", []))
        }
        
        self._set_cache(cache_key, results, ttl=604800)  # 1 week cache
        return results
    
    def get_collection_details(self, collection_id: int) -> Dict[str, Any]:
        """Get details about a movie collection/franchise"""
        cache_key = self._get_cache_key("collection", collection_id=collection_id)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        collection = tmdb.Collection(collection_id)
        info = collection.info()
        
        results = {
            "id": info["id"],
            "name": info["name"],
            "overview": info.get("overview", ""),
            "poster_path": self.get_poster_url(info.get("poster_path", "")),
            "backdrop_path": self.get_poster_url(info.get("backdrop_path", ""), "w1280"),
            "parts": sorted(info.get("parts", []), key=lambda x: x.get("release_date", "") or "")
        }
        
        self._set_cache(cache_key, results, ttl=86400)  # 1 day cache
        return results
    
    def get_keywords_for_content(self, content_id: int, content_type: str = "movie") -> Dict[str, Any]:
        """Get keywords associated with a movie or TV show"""
        cache_key = self._get_cache_key(f"{content_type}_keywords", content_id=content_id)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        if content_type == "movie":
            movie = tmdb.Movie(content_id)
            keywords = movie.keywords()
        else:
            tv = tmdb.TV(content_id)
            keywords = tv.keywords()
        
        results = {
            "id": content_id,
            "keywords": keywords.get("keywords", keywords.get("results", []))
        }
        
        self._set_cache(cache_key, results, ttl=604800)  # 1 week cache
        return results
    
    def get_release_dates(self, movie_id: int) -> Dict[str, Any]:
        """Get regional release dates and certifications for a movie"""
        cache_key = self._get_cache_key("release_dates", movie_id=movie_id)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        movie = tmdb.Movie(movie_id)
        releases = movie.release_dates()
        
        # Organize by region
        results = {
            "id": movie_id,
            "results": {}
        }
        
        for region in releases.get("results", []):
            country = region["iso_3166_1"]
            results["results"][country] = {
                "release_dates": region.get("release_dates", []),
                "certification": next(
                    (r.get("certification") for r in region.get("release_dates", []) 
                     if r.get("certification")), 
                    None
                )
            }
        
        self._set_cache(cache_key, results, ttl=86400)  # 1 day cache
        return results
    
    def get_now_playing(self, region: str = "US", page: int = 1) -> Dict[str, Any]:
        """Get movies currently playing in theaters"""
        cache_key = self._get_cache_key("now_playing", region=region, page=page)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        movies = tmdb.Movies()
        now_playing = movies.now_playing(region=region, page=page)
        
        results = {
            "results": [],
            "dates": now_playing.get("dates", {}),
            "total_results": now_playing.get("total_results", 0)
        }
        
        for movie in now_playing.get("results", []):
            results["results"].append({
                "id": movie["id"],
                "title": movie["title"],
                "release_date": movie.get("release_date", ""),
                "poster_path": self.get_poster_url(movie.get("poster_path", "")),
                "backdrop_path": self.get_poster_url(movie.get("backdrop_path", ""), "w1280"),
                "overview": movie.get("overview", ""),
                "vote_average": movie.get("vote_average", 0),
                "popularity": movie.get("popularity", 0)
            })
        
        self._set_cache(cache_key, results, ttl=3600)  # 1 hour cache for current releases
        return results
    
    def get_recommendations(self, content_id: int, content_type: str = "movie") -> Dict[str, Any]:
        """Get ML-based recommendations (better than similar)"""
        cache_key = self._get_cache_key(f"{content_type}_recommendations", content_id=content_id)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        if content_type == "movie":
            # Use the Movies class to get recommendations
            movies = tmdb.Movies(content_id)
            recs = movies.recommendations()
        else:
            # Use the TV class to get recommendations
            tv = tmdb.TV(content_id)
            recs = tv.recommendations()
        
        results = {
            "results": [],
            "total_results": recs.get("total_results", 0)
        }
        
        for item in recs.get("results", [])[:20]:  # Get top 20 recommendations
            if content_type == "movie":
                results["results"].append({
                    "id": item["id"],
                    "title": item["title"],
                    "release_date": item.get("release_date", ""),
                    "poster_path": self.get_poster_url(item.get("poster_path", "")),
                    "overview": item.get("overview", "")[:200],
                    "vote_average": item.get("vote_average", 0)
                })
            else:
                results["results"].append({
                    "id": item["id"],
                    "name": item["name"],
                    "first_air_date": item.get("first_air_date", ""),
                    "poster_path": self.get_poster_url(item.get("poster_path", "")),
                    "overview": item.get("overview", "")[:200],
                    "vote_average": item.get("vote_average", 0)
                })
        
        self._set_cache(cache_key, results, ttl=86400)  # 1 day cache
        return results
    
    def get_next_episode(self, tv_id: int) -> Dict[str, Any]:
        """Get the next episode to air for a TV show"""
        cache_key = self._get_cache_key("next_episode", tv_id=tv_id)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        tv = tmdb.TV(tv_id)
        info = tv.info(append_to_response="next_episode_to_air,last_episode_to_air")
        
        results = {
            "id": tv_id,
            "next_episode": None,
            "last_episode": None
        }
        
        if info.get("next_episode_to_air"):
            next_ep = info["next_episode_to_air"]
            results["next_episode"] = {
                "id": next_ep.get("id"),
                "name": next_ep.get("name"),
                "season_number": next_ep.get("season_number"),
                "episode_number": next_ep.get("episode_number"),
                "air_date": next_ep.get("air_date"),
                "overview": next_ep.get("overview", ""),
                "still_path": self.get_poster_url(next_ep.get("still_path", ""), "w780")
            }
        
        if info.get("last_episode_to_air"):
            last_ep = info["last_episode_to_air"]
            results["last_episode"] = {
                "id": last_ep.get("id"),
                "name": last_ep.get("name"),
                "season_number": last_ep.get("season_number"),
                "episode_number": last_ep.get("episode_number"),
                "air_date": last_ep.get("air_date"),
                "overview": last_ep.get("overview", ""),
                "still_path": self.get_poster_url(last_ep.get("still_path", ""), "w780")
            }
        
        self._set_cache(cache_key, results, ttl=3600)  # 1 hour cache for episode info
        return results
    
    def get_external_ids(self, content_id: int, content_type: str = "movie") -> Dict[str, Any]:
        """Get external IDs (IMDB, TVDB, etc.) for cross-referencing"""
        cache_key = self._get_cache_key(f"{content_type}_external_ids", content_id=content_id)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        if content_type == "movie":
            movie = tmdb.Movie(content_id)
            ids = movie.external_ids()
        else:
            tv = tmdb.TV(content_id)
            ids = tv.external_ids()
        
        results = {
            "id": content_id,
            "imdb_id": ids.get("imdb_id"),
            "facebook_id": ids.get("facebook_id"),
            "instagram_id": ids.get("instagram_id"),
            "twitter_id": ids.get("twitter_id")
        }
        
        if content_type == "tv":
            results["tvdb_id"] = ids.get("tvdb_id")
            results["tvrage_id"] = ids.get("tvrage_id")
        
        self._set_cache(cache_key, results, ttl=604800)  # 1 week cache
        return results
    
    def find_by_external_id(self, external_id: str, source: str = "imdb_id") -> Dict[str, Any]:
        """Find content by external ID (e.g., IMDB ID)"""
        cache_key = self._get_cache_key("find_external", external_id=external_id, source=source)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        find = tmdb.Find(external_id)
        results = find.info(external_source=source)
        
        self._set_cache(cache_key, results, ttl=86400)  # 1 day cache
        return results
    
    def discover_with_keywords(self, keyword_ids: list, content_type: str = "movie", 
                               page: int = 1, **kwargs) -> Dict[str, Any]:
        """Discover content using keyword IDs"""
        cache_key = self._get_cache_key(
            f"discover_{content_type}_keywords", 
            keywords=",".join(map(str, keyword_ids)),
            page=page,
            **kwargs
        )
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        discover = tmdb.Discover()
        
        params = {
            "with_keywords": ",".join(map(str, keyword_ids)),
            "page": page,
            "sort_by": kwargs.get("sort_by", "popularity.desc")
        }
        
        # Add any additional filters
        for key, value in kwargs.items():
            if key not in ["sort_by"] and value is not None:
                params[key] = value
        
        if content_type == "movie":
            results = discover.movie(**params)
        else:
            results = discover.tv(**params)
        
        self._set_cache(cache_key, results, ttl=3600)  # 1 hour cache
        return results