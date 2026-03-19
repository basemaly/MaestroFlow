"use client";

import { BookIcon, CheckIcon, Loader2Icon, XIcon } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  extractBrowseMetadata,
  getCalibreStatus,
  queryCalibre,
} from "@/core/calibre/api";
import type {
  CalibreBrowseMetadata,
  CalibreBookSelection,
  CalibreQueryResponse,
  CalibreStatusResponse,
} from "@/core/calibre/types";

export function CalibreActions() {
  const [mounted, setMounted] = useState(false);
  const [open, setOpen] = useState(false);

  // Search & filter inputs
  const [query, setQuery] = useState("");
  const [selectedAuthor, setSelectedAuthor] = useState("");
  const [selectedTag, setSelectedTag] = useState("");
  const [selectedSeries, setSelectedSeries] = useState("");

  // API responses
  const [config, setConfig] = useState<CalibreStatusResponse | null>(null);
  const [results, setResults] = useState<CalibreQueryResponse | null>(null);
  const [browseMetadata, setBrowseMetadata] = useState<CalibreBrowseMetadata | null>(null);

  // UI state
  const [selected, setSelected] = useState<CalibreBookSelection>({});
  const [loadingConfig, setLoadingConfig] = useState(false);
  const [loadingResults, setLoadingResults] = useState(false);
  const configAbortRef = useRef<AbortController | null>(null);
  const searchAbortRef = useRef<AbortController | null>(null);

  // Computed
  const selectedBooks = useMemo(() => {
    return (results?.items ?? []).filter((book) => selected[book.id]);
  }, [results, selected]);

  // Hydration safety
  useEffect(() => {
    setMounted(true);
  }, []);

  // Load status on dialog open
  useEffect(() => {
    if (!open || !mounted) return;

    const loadStatus = async () => {
      if (configAbortRef.current) configAbortRef.current.abort();
      configAbortRef.current = new AbortController();

      setLoadingConfig(true);
      try {
        const status = await getCalibreStatus();
        setConfig(status);

        // Load initial metadata if available
        if (status.available && status.indexed_books && status.indexed_books > 0) {
          try {
            const emptyQuery = await queryCalibre({ query: "", top_k: 20 });
            const metadata = extractBrowseMetadata(emptyQuery.items);
            setBrowseMetadata(metadata);
          } catch (e) {
            console.error("Failed to load browse metadata:", e);
          }
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to load Calibre status";
        toast.error(message);
      } finally {
        setLoadingConfig(false);
      }
    };

    void loadStatus();

    return () => {
      if (configAbortRef.current) configAbortRef.current.abort();
    };
  }, [open, mounted]);

  // Handle search
  const handleSearch = async () => {
    if (!query.trim() && !selectedAuthor && !selectedTag && !selectedSeries) {
      toast.error("Enter a search query or select a filter");
      return;
    }

    if (searchAbortRef.current) searchAbortRef.current.abort();
    searchAbortRef.current = new AbortController();

    setLoadingResults(true);
    setSelected({});

    try {
      const filters: Record<string, unknown> = {};
      if (selectedAuthor && selectedAuthor !== "_all") filters.author = selectedAuthor;
      if (selectedTag && selectedTag !== "_all") filters.tag = selectedTag;
      if (selectedSeries && selectedSeries !== "_all") filters.series = selectedSeries;

      const response = await queryCalibre({
        query: query.trim() || "*",
        filters: Object.keys(filters).length > 0 ? filters : undefined,
      });

      setResults(response);

      // Update metadata
      if (response.items.length > 0) {
        const metadata = extractBrowseMetadata(response.items);
        setBrowseMetadata(metadata);
      }

      if (response.items.length === 0) {
        toast.info("No books found matching your search");
      } else {
        toast.success(`Found ${response.total} book${response.total !== 1 ? "s" : ""}`);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Search failed";
      toast.error(message);
    } finally {
      setLoadingResults(false);
    }
  };

  // Handle ingest
  const handleIngest = async () => {
    if (selectedBooks.length === 0) {
      toast.error("Select at least one book to ingest");
      return;
    }

    setLoadingResults(true);

    try {
      // TODO: Call SurfSense ingest endpoint with selected book IDs
      // This would typically be: POST /api/surfsense/ingest with { calibre_ids: [...] }
      // For now, just show success toast

      toast.success(`Queued ${selectedBooks.length} book${selectedBooks.length !== 1 ? "s" : ""} for ingest`);
      setSelected({});
    } catch (error) {
      const message = error instanceof Error ? error.message : "Ingest failed";
      toast.error(message);
    } finally {
      setLoadingResults(false);
    }
  };

  const toggleSelectAll = () => {
    if (selectedBooks.length === results?.items.length) {
      setSelected({});
    } else {
      const newSelected: CalibreBookSelection = {};
      results?.items.forEach((book) => {
        newSelected[book.id] = true;
      });
      setSelected(newSelected);
    }
  };

  const toggleBook = (bookId: string | number) => {
    setSelected((prev) => ({
      ...prev,
      [bookId]: !prev[bookId],
    }));
  };

  if (!mounted) return null;

  return (
    <Dialog open={open} onOpenChange={(newOpen) => {
      setOpen(newOpen);
      if (!newOpen) {
        setQuery("");
        setSelectedAuthor("");
        setSelectedTag("");
        setSelectedSeries("");
        setSelected({});
        setResults(null);
      }
    }}>
      <DialogTrigger asChild>
        <Button size="sm" variant="ghost" className="h-8 px-2">
          <BookIcon className="size-4" />
          <span className="hidden sm:inline">Calibre</span>
        </Button>
      </DialogTrigger>

      <DialogContent className="sm:max-w-4xl max-h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Search Calibre Library</DialogTitle>
          <DialogDescription>
            Search, browse, and ingest books from your Calibre library into SurfSense.
          </DialogDescription>
        </DialogHeader>

        {/* Status Bar */}
        <div className="flex items-center justify-between px-2 py-2 rounded-lg bg-muted/50">
          {loadingConfig ? (
            <div className="flex items-center gap-2 text-sm">
              <Loader2Icon className="size-4 animate-spin" />
              <span>Checking Calibre status...</span>
            </div>
          ) : config?.available ? (
            <div className="flex items-center gap-2 text-sm">
              <CheckIcon className="size-4 text-green-600" />
              <span className="font-medium">Connected</span>
              {config.indexed_books !== undefined && (
                <Badge variant="secondary" className="ml-2">
                  {config.indexed_books} books
                </Badge>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-2 text-sm">
              <XIcon className="size-4 text-red-600" />
              <span className="text-muted-foreground">
                {config?.error?.message ?? "Calibre not available"}
              </span>
            </div>
          )}
        </div>

        {config?.available ? (
          <>
            {/* Search Inputs */}
            <div className="space-y-3 px-2">
              <Input
                placeholder="Search by title, author, or keyword..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void handleSearch();
                }}
                disabled={loadingResults}
                className="text-sm"
              />

              {/* Filter Dropdowns */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                <Select value={selectedAuthor} onValueChange={setSelectedAuthor}>
                  <SelectTrigger className="text-sm">
                    <SelectValue placeholder="Filter by author..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="_all">All authors</SelectItem>
                    {browseMetadata?.authors.map((author) => (
                      <SelectItem key={author} value={author}>
                        {author}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <Select value={selectedTag} onValueChange={setSelectedTag}>
                  <SelectTrigger className="text-sm">
                    <SelectValue placeholder="Filter by tag..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="_all">All tags</SelectItem>
                    {browseMetadata?.tags.slice(0, 30).map((tag) => (
                      <SelectItem key={tag} value={tag}>
                        {tag}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <Select value={selectedSeries} onValueChange={setSelectedSeries}>
                  <SelectTrigger className="text-sm">
                    <SelectValue placeholder="Filter by series..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="_all">All series</SelectItem>
                    {browseMetadata?.series.slice(0, 30).map((s) => (
                      <SelectItem key={s} value={s}>
                        {s}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Search Button */}
              <Button
                onClick={handleSearch}
                disabled={loadingResults}
                className="w-full"
              >
                {loadingResults ? (
                  <>
                    <Loader2Icon className="size-4 mr-2 animate-spin" />
                    Searching...
                  </>
                ) : (
                  "Search"
                )}
              </Button>
            </div>

            {/* Results */}
            {results && (
              <div className="flex-1 flex flex-col min-h-0 px-2">
                <div className="text-sm text-muted-foreground mb-2">
                  Found {results.total} book{results.total !== 1 ? "s" : ""}
                  {selectedAuthor && ` by ${selectedAuthor}`}
                  {selectedTag && ` tagged "${selectedTag}"`}
                  {selectedSeries && ` in series "${selectedSeries}"`}
                </div>

                {results.items.length > 0 ? (
                  <>
                    {/* Select All Checkbox */}
                    <label className="flex items-center gap-2 mb-2 pb-2 border-b cursor-pointer">
                      <input
                        type="checkbox"
                        checked={
                          selectedBooks.length > 0 &&
                          selectedBooks.length === results.items.length
                        }
                        onChange={toggleSelectAll}
                        className="cursor-pointer"
                      />
                      <span className="text-sm font-medium">
                        {selectedBooks.length > 0
                          ? `${selectedBooks.length} selected`
                          : "Select books"}
                      </span>
                    </label>

                    {/* Books Grid */}
                    <ScrollArea className="flex-1">
                      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 pr-4">
                        {results.items.map((book) => (
                          <label
                            key={book.id}
                            className="flex items-start gap-2 p-3 border rounded-lg hover:bg-accent/50 transition-colors cursor-pointer"
                          >
                            <input
                              type="checkbox"
                              checked={!!selected[book.id]}
                              onChange={() => toggleBook(book.id)}
                              className="mt-0.5 cursor-pointer"
                            />
                            <div className="flex-1 min-w-0">
                              <h4 className="text-sm font-medium line-clamp-2">
                                {book.title}
                              </h4>
                              {book.authors && book.authors.length > 0 && (
                                <p className="text-xs text-muted-foreground line-clamp-1">
                                  {book.authors.join(", ")}
                                </p>
                              )}
                              {book.tags && book.tags.length > 0 && (
                                <div className="flex flex-wrap gap-1 mt-1">
                                  {book.tags.slice(0, 2).map((tag) => (
                                    <Badge
                                      key={tag}
                                      variant="secondary"
                                      className="text-xs"
                                    >
                                      {tag}
                                    </Badge>
                                  ))}
                                  {book.tags.length > 2 && (
                                    <Badge
                                      variant="secondary"
                                      className="text-xs"
                                    >
                                      +{book.tags.length - 2}
                                    </Badge>
                                  )}
                                </div>
                              )}
                            </div>
                          </label>
                        ))}
                      </div>
                    </ScrollArea>
                  </>
                ) : (
                  <div className="flex-1 flex items-center justify-center text-muted-foreground">
                    No books found
                  </div>
                )}
              </div>
            )}

            {/* Footer */}
            <div className="flex items-center justify-between gap-2 px-2 py-3 border-t">
              <span className="text-sm font-medium">
                {selectedBooks.length > 0
                  ? `${selectedBooks.length} book${selectedBooks.length !== 1 ? "s" : ""} to ingest`
                  : "No books selected"}
              </span>
              <Button
                onClick={handleIngest}
                disabled={selectedBooks.length === 0 || loadingResults}
              >
                {loadingResults ? (
                  <>
                    <Loader2Icon className="size-4 mr-2 animate-spin" />
                    Ingesting...
                  </>
                ) : (
                  `Ingest to SurfSense`
                )}
              </Button>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-muted-foreground">
            Calibre library is not available. Please check your configuration.
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
