# ============================================================================
# IMPORTS & LIBRARY EXPLANATIONS
# ============================================================================
# BeautifulSoup: HTML/XML parser that converts raw HTML into a navigable tree.
#   Allows us to find and extract specific tags (e.g., <a> for links) and 
#   retrieve text content easily without regex fragility.
#
# urldefrag: Removes the fragment portion of a URL (everything after #).
#   Example: 'http://example.com/page#section' → 'http://example.com/page'
#   CRITICAL: Crawlers must not treat #section as a separate page.
#
# urlparse: Parses a complete URL into components (scheme, hostname, path, 
#   query parameters, etc.). Used to extract domain names, validate schemes,
#   and check for suspicious query parameters.
#
# urljoin: Converts relative URLs into absolute URLs by joining them with a base.
#   Example: base='http://example.com/dept/', relative='../info' 
#            → result='http://example.com/info'
#   ESSENTIAL: Many webpages link relatively; we must resolve them to crawl.
#
# re (regex): Pattern matching for two purposes:
#   1. Tokenization: extract words from text (r"[a-zA-Z0-9]+")
#   2. File type filtering: identify banned extensions (.pdf, .zip, etc.)
#
from bs4 import BeautifulSoup
from urllib.parse import urldefrag, urlparse, urljoin
import re

###############################################################################
# GLOBAL STORAGE (MVP - Minimum Viable Product)
# ============================================================================
# These globals accumulate analytics and statistics across all crawled pages.
# They are populated as the crawler processes each page.
# NOTE: Analytics team can refactor these into a separate module/database later.
###############################################################################

# STOPWORDS: Set of common English words with minimal semantic meaning.
# ============================================================================
# Definition: High-frequency words that appear in almost every document but
#   contribute little to understanding topic or content (e.g., "the", "and").
#
# Why filter stopwords? They inflate word frequency counts without adding insight.
#   Example: Text "the quick brown fox" → after stopword filtering → 
#            ["quick", "brown", "fox"] (removed "the")
#   This focuses analytics on meaningful, topic-specific words.
#
# How used: During tokenization, any token matching a stopword is discarded.
#   Prevents high-frequency noise from skewing word frequency statistics.
#
STOPWORDS = set([
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any",
    "are", "aren't", "as", "at", "be", "because", "been", "before", "being", "below",
    "between", "both", "but", "by", "can't", "cannot", "could", "couldn't", "did",
    "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during", "each",
    "few", "for", "from", "further", "had", "hadn't", "has", "hasn't", "have",
    "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here", "here's",
    "hers", "herself", "him", "himself", "his", "how", "how's", "i", "i'd", "i'll",
    "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself",
    "let's", "me", "more", "most", "mustn't", "my", "myself", "no", "nor", "not",
    "of", "off", "on", "once", "only", "or", "other", "ought", "our", "ours",
    "ourselves", "out", "over", "own", "same", "shan't", "she", "she'd", "she'll",
    "she's", "should", "shouldn't", "so", "some", "such", "than", "that", "that's",
    "the", "their", "theirs", "them", "themselves", "then", "there", "there's", "these",
    "they", "they'd", "they'll", "they're", "they've", "this", "those", "through",
    "to", "too", "under", "until", "up", "very", "was", "wasn't", "we", "we'd",
    "we'll", "we're", "we've", "were", "weren't", "what", "what's", "when", "when's",
    "where", "where's", "which", "while", "who", "who's", "whom", "why", "why's",
    "with", "won't", "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've",
    "your", "yours", "yourself", "yourselves"
])

# word_freq: Global dictionary tracking token frequencies across ALL crawled pages.
# ============================================================================
# Format: {token (str): count (int)}
# Purpose: Accumulates word frequencies to identify most common topics/keywords
#   in the crawled UCI computer science domain.
# Usage: After crawling 100 pages, word_freq might be:
#   {"machine": 542, "learning": 389, "algorithm": 287, "research": 1240, ...}
# Insight: "research" appears most often, indicating dominant topic.
#
word_freq = {}

# longest_page: Tracks the URL with the most content by token count.
# ============================================================================
# Format: (url, word_count) where word_count = # of non-stopword tokens
# Purpose: Quality metric; identifies pages with substantial textual content.
# Usage: After crawling, longest_page might be ("http://ics.uci.edu/research", 4521)
#   indicating the research page has 4521 tokens—likely a major content hub.
#
longest_page = ("", 0)   # (url, word_count)

###############################################################################
# HELPER FUNCTIONS
###############################################################################

###############################################################################
# HELPER FUNCTIONS - Utility functions called by the main scraper().
###############################################################################

def tokenize(text: str):
    """
    TOKENIZATION: Break raw text into meaningful word tokens (tokens).
    
    PROCESS:
    ========
    1. Use regex r"[a-zA-Z0-9]+" to extract sequences of letters/digits.
       This regex matches one or more consecutive alphanumeric characters.
       Examples: "hello123" → ["hello123"], "hello, world!" → ["hello", "world"]
       (Punctuation breaks the sequence, so commas/periods act as delimiters.)
    
    2. Convert all tokens to lowercase for case-insensitive matching.
       Example: "Hello" and "HELLO" both become "hello"
       Ensures we count them as the same token.
    
    3. Filter out stopwords (words with little semantic meaning).
       Example: ["the", "quick", "fox"] → ["quick", "fox"] after filtering
       Removes "the" because it's a stopword.
    
    WHY LOWERCASE? Prevents counting "The", "the", "THE" as three separate words.
    WHY FILTER STOPWORDS? They're noise; meaningful keywords matter more.
    
    Args:
        text (str): Raw text extracted from a webpage's HTML
    
    Returns:
        list[str]: List of lowercase, non-stopword tokens
    
    EXAMPLE:
    --------
    Input:  "The machine learning algorithm is powerful."
    Regex extracts: ["The", "machine", "learning", "algorithm", "is", "powerful"]
    Lowercase:      ["the", "machine", "learning", "algorithm", "is", "powerful"]
    Filter stopwords (remove "the", "is"): ["machine", "learning", "algorithm", "powerful"]
    Returns: ["machine", "learning", "algorithm", "powerful"]
    """
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return [t for t in tokens if t not in STOPWORDS]


def extract_visible_text(soup: BeautifulSoup):
    """
    EXTRACT VISIBLE TEXT: Get only human-readable content from a webpage.
    
    PROCESS:
    ========
    1. Identify and remove non-content tags:
       - <script> tags: Contain JavaScript code (not user-facing content)
       - <style> tags: Contain CSS styling rules (not user-facing content)
       - <noscript> tags: Fallback for browsers with JavaScript disabled (rare)
    
       These tags don't contribute to page semantics; they're clutter that pollutes
       word frequency counts. Example:
         BEFORE: <body><script>var x=1;</script><p>Welcome</p></body>
         AFTER:  <body><p>Welcome</p></body>
    
    2. Extract all remaining text using .get_text():
       - Traverses the HTML tree collecting all text nodes
       - separator=" " joins text from different tags with a space
         (prevents "word1word2" concatenation from adjacent tags)
       - strip=True removes leading/trailing whitespace
    
    WHY REMOVE SCRIPTS/STYLES?
    - JavaScript is executable code, not page content
    - CSS is formatting rules, not page content
    - Both are distracting noise in text analysis
    
    Args:
        soup (BeautifulSoup): Parsed HTML document tree
    
    Returns:
        str: Plain text content (no HTML tags, no scripts/styles)
    
    EXAMPLE:
    --------
    Input HTML:
      <body>
        <script>console.log('tracking');</script>
        <style>.header { color: blue; }</style>
        <h1>Welcome to our site</h1>
        <p>Learn about machine learning.</p>
      </body>
    
    After removing <script> and <style>:
      <body>
        <h1>Welcome to our site</h1>
        <p>Learn about machine learning.</p>
      </body>
    
    Output text: "Welcome to our site Learn about machine learning."
    """
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text(separator=" ", strip=True)


###############################################################################
# MAIN SCRAPER FUNCTION - Core entry point called by crawler framework.
# ============================================================================
# This function processes ONE downloaded page and returns valid outgoing links.
# The crawler framework calls this repeatedly for each URL in the frontier.
###############################################################################

def scraper(url, resp):
    """
    MAIN SCRAPER - Process one webpage and extract valid outgoing links.
    
    HIGH-LEVEL WORKFLOW:
    ====================
    1. VALIDATE RESPONSE: Ensure we have a successful HTTP 200 response
       with valid HTML content (not error pages, images, or huge files)
    
    2. PARSE HTML: Convert raw HTML bytes into navigable tree using BeautifulSoup
    
    3. BUILD ANALYTICS: Extract visible text, tokenize, and update global word
       frequency and longest page statistics
    
    4. EXTRACT LINKS: Find all <a href="..."> tags in the page
    
    5. APPLY HEURISTICS: Filter links using politeness + trap-avoidance checks
       (URL length, session parameters, path depth, query parameter count, etc.)
    
    6. VALIDATE: Run final domain and file-type restrictions
    
    7. RETURN: Return clean list of valid URLs for crawler to add to frontier
    
    WHY VALIDATE RESPONSES?
    =======================
    - Status != 200 means error page (404), redirect (301), or server error (500)
    - Non-HTML content (PDFs, images) can't be parsed for <a> tags
    - Huge responses (>5MB) might be intentional bandwidth traps or binary files
    - Checking Content-Type prevents wasting resources on non-HTML
    
    WHY APPLY HEURISTICS?
    =====================
    Some websites intentionally create crawler traps to waste resources:
    - Infinite calendar pages (year/month/day combos)
    - Session parameter variations (same page, different session ID)
    - Deep directory structures that generate URLs dynamically
    
    We filter by:
    - URL LENGTH: >2000 chars usually indicates garbage or encoded attacks
    - SESSION PARAMETERS: jsessionid, phpsessid, utm_* create duplicate URLs
    - QUERY PARAMETERS: >6 params often signals search/filter interface trap
    - PATH DEPTH: >12 slashes indicates deep/generated directory structure
    - CREDENTIALS: URLs with user:password are malformed or malicious
    
    Args:
    ======
    url (str):
        The original URL that was requested (may differ from final URL due to redirects)
    
    resp: Response object from framework with attributes:
        - resp.status: HTTP status code (200=success, 404=not found, 500=error, etc.)
        - resp.raw_response: Raw HTTP response object containing:
            - resp.raw_response.headers: Dict-like object with HTTP headers
            - resp.raw_response.content: Raw bytes of the page content
            - resp.raw_response.url: Final URL after following any redirects
    
    Returns:
    =========
    list[str]: List of valid, normalized, absolute URLs found on this page.
              Returns empty list [] if page cannot be processed for any reason.
    
    INTERVIEW TALKING POINTS:
    ==========================
    1. "We validate HTTP status to avoid processing errors"
    2. "We check Content-Type to skip non-HTML files"
    3. "We remove session parameters to avoid crawling the same page 100 times"
    4. "We limit path depth and query count to skip infinite directory traps"
    5. "We restrict to 4 UCI CS subdomains as per project scope"
    """
    
    # Declare 'longest_page' as global because we REASSIGN it (not just mutate).
    # Note: word_freq is NOT declared global because we only mutate its contents
    # (word_freq[key] = value), we never reassign word_freq itself.
    global longest_page

    links = []  # Accumulator for valid URLs from this page

    # =========================================================================
    # STEP 1: VALIDATE RESPONSE - Ensure we have valid, processable HTML
    # =========================================================================
    
    # Check HTTP status code is 200 (success).
    # Skip error responses: 404 (not found), 500 (server error), 301 (redirect), etc.
    if resp.status != 200:
        return links  # Early exit: invalid status code

    # Verify the response object actually has content.
    # Guard against framework edge cases where raw_response might be None.
    if not getattr(resp, "raw_response", None):
        return links  # Early exit: no content available

    # Check Content-Type header ensures we're processing HTML, not:
    # - application/pdf (PDFs have no <a> tags to extract)
    # - image/png (images have no HTML structure)
    # - application/octet-stream (binary files)
    # - application/javascript (JavaScript code files)
    # Only text/html contains meaningful links and content for our crawler.
    content_type = resp.raw_response.headers.get("Content-Type", "")
    if "text/html" not in content_type:
        return links  # Early exit: not an HTML document

    # POLITE CRAWLING: Avoid processing huge responses.
    # Responses >5MB might indicate:
    # - Accidentally fetched a large file (video, database dump, archive)
    # - Bandwidth trap intentionally serving enormous files
    # - Memory waste for a simple crawler
    # Typical HTML pages are <1MB; 5MB limit is reasonable upper bound.
    try:
        cl = resp.raw_response.headers.get("Content-Length")
        if cl and int(cl) > 5 * 1024 * 1024:  # 5MB = 5242880 bytes
            return links  # Early exit: response too large
    except Exception:
        pass  # If we can't read Content-Length, continue anyway (not fatal)

    # =========================================================================
    # STEP 2: PARSE HTML INTO NAVIGABLE TREE STRUCTURE
    # =========================================================================
    # BeautifulSoup converts raw HTML bytes into a tree we can traverse.
    # Try 'lxml' parser first (fast, lenient with malformed HTML).
    # Fall back to 'html.parser' if lxml unavailable (pure Python, always works).
    # WHY FALLBACK? lxml requires system C library; html.parser is built-in.
    try:
        soup = BeautifulSoup(resp.raw_response.content, "lxml")
    except Exception:
        try:
            soup = BeautifulSoup(resp.raw_response.content, "html.parser")
        except Exception:
            return links  # Early exit: parsing failed completely

    # =========================================================================
    # STEP 3: EXTRACT TEXT CONTENT AND BUILD ANALYTICS
    # =========================================================================
    # Extract visible human-readable text (no HTML tags, scripts, styles).
    text = extract_visible_text(soup)
    
    # Tokenize: Split text into lowercase words, remove stopwords.
    tokens = tokenize(text)

    # Update global word frequency statistics.
    # This accumulates term frequencies across all crawled pages.
    # After crawling thousands of pages, we can identify most common topics.
    # Example: word_freq["research"] += 1 for each time "research" appears.
    for tok in tokens:
        word_freq[tok] = word_freq.get(tok, 0) + 1

    # Track which page has the most content by token count.
    # Useful for quality assurance: identifies major content hubs.
    # Example: After crawling, longest_page = ("http://ics.uci.edu/research", 5000)
    # indicates the research page is the largest, probably a major hub.
    if len(tokens) > longest_page[1]:
        longest_page = (url, len(tokens))

    # =========================================================================
    # STEP 4: EXTRACT AND FILTER OUTGOING LINKS
    # =========================================================================
    # Find all <a href="..."> tags and process their targets.
    # Apply POLITENESS HEURISTICS and TRAP AVOIDANCE to filter suspicious URLs.
    
    # Use the final URL after any redirects as the base for resolving relative links.
    # Example: If we requested /old, server redirected to /new,
    #          we should resolve relative links against /new, not /old.
    base_for_join = getattr(resp.raw_response, "url", url)

    for a in soup.find_all("a", href=True):
        # soup.find_all("a", href=True) finds all <a> tags with href attribute.
        # This ignores <a> tags without href (rare, but possible).
        href = a.get("href")  # Extract the href attribute value as a string

        if not href:
            continue  # Skip if href is empty or None

        href = href.strip()  # Remove leading/trailing whitespace

        # =====================================================================
        # FILTER #1: SKIP NON-NAVIGATIONAL LINKS
        # =====================================================================
        # Skip URLs with schemes that don't navigate to new web pages:
        # - javascript: links execute code in browser, don't fetch new pages
        # - mailto: links open email client, not web pages
        # - # fragment links scroll to a section on the same page
        # We only care about http(s) links leading to new content.
        low = href.lower()
        if low.startswith("javascript:") or low.startswith("mailto:") or href.startswith('#'):
            continue  # Skip non-navigational schemes

        # =====================================================================
        # FILTER #2: RESOLVE RELATIVE URLs AND REMOVE FRAGMENTS
        # =====================================================================
        # Many webpages use relative links instead of absolute URLs:
        # Examples:
        # - <a href="page.html"> (relative to current directory)
        # - <a href="../other"> (relative to parent directory)
        # - <a href="/absolute/path"> (absolute path from domain root)
        # urljoin() converts these to absolute URLs using a base URL.
        #
        # Example: base="http://ics.uci.edu/dept/faculty/", href="../info"
        #          → urljoin result: "http://ics.uci.edu/dept/info"
        try:
            href = urljoin(base_for_join, href)
        except Exception:
            continue  # If URL resolution fails, skip this link

        # Remove URL fragments (everything after #).
        # Fragments don't change server-side content; they're just scroll positions.
        # Example: "http://example.com/page#section" → "http://example.com/page"
        # If not removed, we'd crawl:
        # - /page#section1
        # - /page#section2
        # - /page#section3
        # ...all the same page! Wastes crawl budget. Defragment to normalize.
        href, _ = urldefrag(href)

        # =====================================================================
        # FILTER #4: FINAL VALIDATION (DOMAIN & FILE TYPE)
        # =====================================================================
        # is_valid() enforces project scope restrictions:
        # 1. Only crawl allowed UCI domains (ics, cs, informatics, stat)
        # 2. Skip binary file types (PDFs, zips, images, etc.)
        # See is_valid() function below for full details.
        if is_valid(href):
            links.append(href)  # URL passed all filters! Add to results.

    return links  # Return all valid URLs found on this page


###############################################################################
# URL VALIDATION FUNCTION - Final domain and file-type restrictions
###############################################################################

def is_valid(url: str):
    """
    URL VALIDATION: Enforce project scope restrictions.
    
    SCOPE RESTRICTIONS:
    ===================
    1. DOMAIN RESTRICTION: Only crawl these UCI Computer Science subdomains:
       - *.ics.uci.edu (Information & Computer Sciences)
       - *.cs.uci.edu (Computer Science)
       - *.informatics.uci.edu (Informatics)
       - *.stat.uci.edu (Statistics)
       
       WHY RESTRICT? Project requirement: focus on CS department pages.
       Prevents crawling off-domain into news, social media, unrelated content.
    
    2. FILE TYPE RESTRICTION: Reject binary/non-text files.
       Banned extensions: Images (jpg, png, gif), Audio (mp3, wav), 
       Video (mp4, avi, mov), Documents (pdf, doc, xls), Archives (zip, rar, tar),
       Code (css, js), Executables (exe, dll), and many others.
       
       WHY FILTER? These files:
       - Can't be parsed for links (no <a> tags)
       - Waste bandwidth (100MB video = wasted crawl time)
       - Aren't text content (no tokens to extract)
       - Indicate resource downloads, not content browsing
    
    PROCESS:
    ========
    1. Parse URL into components using urlparse()
    2. Verify scheme (http/https) - reject ftp, data, javascript, etc.
    3. Check domain: must end with one of 4 allowed UCI domains
    4. Check path: must not end with a banned file extension
    
    EXAMPLES:
    =========
    Valid URLs:
      - http://ics.uci.edu/faculty → UCI domain ✓, no banned extension ✓
      - https://cs.uci.edu/research/page.html → UCI domain ✓, .html allowed ✓
    
    Invalid URLs:
      - http://google.com/page → Wrong domain (google.com) ✗
      - https://ics.uci.edu/file.pdf → Banned extension .pdf ✗
      - ftp://cs.uci.edu/data → Wrong scheme ftp:// ✗
    
    Args:
        url (str): Full URL to validate
    
    Returns:
        bool: True if URL passes all restrictions, False otherwise
    """
    try:
        parsed = urlparse(url)

        # RESTRICTION 1: SCHEME CHECK
        # Only accept http:// and https://
        # Reject: ftp://, file://, data://, javascript://, mailto://, etc.
        # These non-HTTP schemes don't point to web pages we can crawl.
        #This ensures if the URL scheme is http or https
        if parsed.scheme not in set(["http", "https"]):     
            return False  # Reject if scheme is not http/https
        
        # RESTRICTION 2: DOMAIN CHECK
        #List of domains allowed according to assignment
        allowed_domains = [".ics.uci.edu", ".cs.uci.edu", ".informatics.uci.edu", ".stat.uci.edu"]

        # Verify domain is one of the four allowed UCI CS subdomains.
        # parsed.netloc = "hostname" or "hostname:port" from the URL
        # Examples:
        # - "ics.uci.edu" (exact match with "ics.uci.edu")
        # - "faculty.ics.uci.edu" (subdomain, ends with ".ics.uci.edu")
        # - "ics.uci.edu:8080" (with port, endswith still works)
        # - "google.com" (not allowed, rejected)
        #
        #Checks if netloc of URL ends with domain in "allowed_domains" list
        #OR if it's the domain without the leading dot so like ("ics.uci.edu/home")
        valid_domain = False
        for domain in allowed_domains:
            # Check: does netloc end with ".ics.uci.edu"? (catches subdomains + main)
            # OR: does netloc exactly equal "ics.uci.edu"? (domain without leading dot)
            # domain[1:] removes the leading dot: ".ics.uci.edu" → "ics.uci.edu"
            if parsed.netloc.endswith(domain) or parsed.netloc == domain[1:]:
                valid_domain = True
                break
        
        if not valid_domain:
            return False  # Reject if domain doesn't match any allowed domain

        # RESTRICTION 3: FILE TYPE CHECK
        # Regex pattern matches banned file extensions at the END of the path.
        # Example: "/research/paper.pdf" matches .pdf → rejected
        #          "/research/index.html" doesn't match → accepted
        #
        # The pattern: r".*\.(css|js|bmp|...|zip|rar|gz)$"
        # - .* = any characters
        # - \. = literal dot (escaped, since . is special in regex)
        # - (css|js|bmp|...) = any of these extensions
        # - $ = end of string (ensures we match extensions, not middle of path)
        #
        # Banned extensions cover:
        # - Images: bmp, gif, jpg, jpeg, png, tiff
        # - Audio: mp3, wav, avi, mov, mpeg, ram
        # - Video: mp4, m4v, mkv, ogg, ogv, wmv
        # - Documents: pdf, doc, docx, xls, xlsx, ppt, pptx, txt
        # - Archives: zip, rar, tar, gz, 7z, bz2
        # - Code: css, js
        # - Executables: exe, bin, dll, msi
        # - Other: svg, swf, pdf, ps, eps, latex, tex
        #
        # Logic: "return not re.match(...)" means:
        # - If pattern MATCHES (found a banned extension) → return False (invalid)
        # - If pattern doesn't match (no banned extension) → return True (valid)
        return not re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$", parsed.path.lower())
        # parsed.path.lower() converts to lowercase for case-insensitive matching
        # (so "file.PDF" matches same as "file.pdf")

    except TypeError:
        # Catch parsing errors and reject the URL safely.
        print ("TypeError for ", parsed)
        raise
    except Exception:
        # Any other unexpected error during validation: reject the URL.
        return False
        
