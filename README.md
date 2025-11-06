# Distributed Twitter Crawler & Rate Limit Manager

`Python` `Tweepy` `Distributed-Systems` `Networking` `API-Management` `Load-Balancing`

## 1\. Project Overview

This project is an advanced Twitter crawler designed to overcome the platform's stringent API rate limits. Standard crawlers using a single API token are easily blocked or forced into long (15-minute) cooldown periods, especially when fetching high-volume data like all retweeters for a popular tweet.

This system solves that problem by implementing a **distributed client pool**. It manages multiple Twitter API tokens as a shared network resource, intelligently rotating between them based on their individual rate limit cooldowns. This architecture allows the crawler to maximize data throughput and operate continuously with minimal downtime.

## 2\. System Architecture & Core Logic

The system's design is centered on **stateful resource management** to navigate network-level API constraints.

### 2.1. `ClientManager`: The Stateful Resource Pool

This is the core of the networking solution. It does not just store a list of clients; it manages a **stateful pool of network resources** (API tokens).

  * **Initialization:** On startup, `ClientManager` reads all available API credentials from `account_setting.csv` and instantiates a `tweepy.Client` object for each.
  * **State Tracking:** Each client is wrapped in a `TweepyClient` dataclass, which tracks one critical piece of state: `last_used_time`. This timestamp records the exact moment a client either hit a rate limit or completed a high-cost request.

### 2.2. Time-Based Load Balancing: The Core Algorithm

The system's intelligence is in the `get_retweeters_info` function. When a high-volume task (like fetching retweeters) begins, it does not use a simple round-robin or random client. Instead, it executes a **time-based load balancing strategy**:

1.  **Sort:** It calls `client_manager.sort_clients_by_limit_time()`. This custom sort function prioritizes clients whose `last_used_time` is the *oldest* (or `None`, if never used).
2.  **Select:** It selects the client at the top of this sorted list (`clients[0]`)—the "freshest" client available.
3.  **Check State:**
      * **If `last_used_time` is `None` (Fresh):** The client is used immediately.
      * **If `last_used_time` is set (Used):** The system calculates the elapsed time since its last use. If the 15-minute API window has not yet passed, it calculates the *exact remaining sleep time* (e.g., 4 minutes) and sleeps for only that duration.
4.  **Execute & Update:** The client then executes its requests (batched using `tweepy.Paginator` for efficiency). After the request is complete, or if it triggers a `TooManyRequests` exception, its `last_used_time` is updated to the current time, and it is placed back into the pool.

This strategy ensures the system **minimizes idle time**. Instead of *all* processes sleeping for 15 minutes, it only sleeps for the shortest time necessary to free up the next available client, dramatically increasing crawl speed.

### 2.3. Resilient Network Error Handling

The system is built to be resilient to the primary network failure case: API rate limiting.

  * **Graceful Recovery:** `try...except tweepy.errors.TooManyRequests` blocks are implemented in all key API call functions (`get_uids`, `get_recent_user_tweets_data`).
  * **Intelligent Sleep:** Instead of crashing or exiting, the application catches this exception, logs the event, updates the client's `last_used_time`, and either sleeps or rotates to the next available client, ensuring the crawl continues uninterrupted.

## 3\. Tech Stack

  * **Core:** Python
  * **Twitter API Wrapper:** Tweepy
  * **Data Handling:** Pandas
  * **Logging:** Custom Logger Module
