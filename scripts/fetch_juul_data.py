#!/usr/bin/env python3
"""
Script to fetch JUUL Labs email documents from the Industry Documents Library
using the IDL Solr API, following the tutorial approach.
"""

import requests
import json
import time
import pandas as pd
from pathlib import Path
import argparse
from typing import List, Dict, Any
import urllib.parse

class IndustryDocsSearch:
    """Client for the Industry Documents Library Solr API."""

    def __init__(self):
        self.base_url = 'https://metadata.idl.ucsf.edu/solr/ltdl3/query'
        self.results = []
        self.session = requests.Session()
        # Set a reasonable timeout
        self.timeout = 30

    def query(self, q: str, n: int = 1000, batch_size: int = 100):
        """
        Query the IDL API for documents.

        Args:
            q: Solr query string
            n: Maximum number of results to fetch
            batch_size: Number of results per API request (API returns max 100)
        """
        self.results = []
        # API always returns 100 docs max, regardless of rows parameter
        actual_batch_size = 100

        print(f"Querying for up to {n} documents with query: {q}")
        print(f"Note: API returns maximum 100 documents per request")

        start = 0
        total_collected = 0
        batch_num = 1

        while total_collected < n:
            remaining = n - total_collected
            # Always request 100 since that's what the API returns
            params = {
                'q': q,
                'rows': 100,  # API returns max 100 anyway
                'start': start,
                'wt': 'json'
            }

            try:
                print(f"Fetching batch {batch_num}: up to 100 documents (start={start}, collected so far: {total_collected})")
                response = self.session.get(self.base_url, params=params, timeout=self.timeout)

                if response.status_code != 200:
                    print(f"API request failed with status {response.status_code}: {response.text}")
                    break

                data = response.json()

                docs = data.get('response', {}).get('docs', [])
                if not docs:
                    print("No more documents found")
                    break

                # Only take what we need
                docs_to_add = docs[:remaining]
                self.results.extend(docs_to_add)
                batch_collected = len(docs_to_add)
                total_collected += batch_collected

                print(f"Collected {batch_collected} documents from this batch (total: {total_collected}/{n})")

                # If we got fewer than 100, we've reached the end of results
                if len(docs) < 100:
                    print("Reached end of available documents")
                    break

                # If we didn't take all docs from this batch, we're done
                if batch_collected < len(docs):
                    break

                start += 100
                batch_num += 1

                # Be respectful to the API
                time.sleep(0.5)

            except Exception as e:
                print(f"Error fetching batch: {e}")
                break

        print(f"Query complete. Total documents collected: {len(self.results)}")

    def save(self, filename: str, format: str = 'parquet'):
        """
        Save results to file.

        Args:
            filename: Output filename
            format: 'parquet' or 'json'
        """
        if not self.results:
            print("No results to save")
            return

        df = pd.DataFrame(self.results)

        if format.lower() == 'parquet':
            df.to_parquet(filename, index=False)
            print(f"Saved {len(self.results)} documents to {filename}")
        elif format.lower() == 'json':
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, indent=2, ensure_ascii=False)
            print(f"Saved {len(self.results)} documents to {filename}")
        else:
            raise ValueError(f"Unsupported format: {format}")

def main():
    parser = argparse.ArgumentParser(description='Fetch JUUL Labs documents from Industry Documents Library')
    parser.add_argument('--query', '-q', default='(case:"State of North Carolina" AND collection:"JUUL Labs Collection" AND type:Email)',
                       help='Solr query string')
    parser.add_argument('--max-results', '-n', type=int, default=100000,
                       help='Maximum number of documents to fetch')
    parser.add_argument('--batch-size', '-b', type=int, default=1000,
                       help='Batch size for API requests (max 1000)')
    parser.add_argument('--output', '-o', default='juul_nc_emails.parquet',
                       help='Output filename')
    parser.add_argument('--format', '-f', choices=['parquet', 'json'], default='parquet',
                       help='Output format')

    args = parser.parse_args()

    # Create the client
    wrapper = IndustryDocsSearch()

    # Execute the query
    wrapper.query(q=args.query, n=args.max_results, batch_size=args.batch_size)

    # Save the results
    if wrapper.results:
        wrapper.save(args.output, format=args.format)
        print(f"\nDataset saved to {args.output}")
        print(f"Total documents: {len(wrapper.results)}")

        # Show sample of first result
        if wrapper.results:
            print("\nSample document metadata:")
            sample = wrapper.results[0]
            for key, value in list(sample.items())[:10]:  # Show first 10 fields
                print(f"  {key}: {value}")
            if len(sample) > 10:
                print(f"  ... and {len(sample) - 10} more fields")
    else:
        print("No documents found matching the query")

if __name__ == '__main__':
    main()
