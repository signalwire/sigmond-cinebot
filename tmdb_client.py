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
                    "site": video["site"]
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