import requests
import pandas as pd
from duckduckgo_search import DDGS
import re
from bs4 import BeautifulSoup
import os
import google.generativeai as genai
from typing import List, Dict, Any

# Set up Google Gemini API - you'll need an API key
# Get one from: https://aistudio.google.com/app/apikey
GOOGLE_API_KEY = "AIzaSyDLUR8Xye5z4zuvBJ_zaQVupmcYbovcgeg"  # Replace with your actual API key
genai.configure(api_key=GOOGLE_API_KEY)

class SearchAgent:
    """Agent responsible for searching DuckDuckGo and retrieving information."""
    
    def __init__(self):
        self.ddgs = DDGS()
        
    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Search DuckDuckGo for the given query and return results."""
        print(f"SearchAgent: Searching for '{query}'...")
        results = []
        
        try:
            search_results = self.ddgs.text(query, max_results=max_results)
            
            for r in search_results:
                result = {
                    'title': r.get('title', ''),
                    'url': r.get('href', ''),
                    'snippet': r.get('body', '')
                }
                
                # Get content from URL (optional - can be disabled to speed up process)
                try:
                    content = self.extract_content(result['url'])
                    result['content'] = content[:5000]  # Limit content size
                except Exception as e:
                    print(f"Warning: Couldn't extract content from {result['url']}: {e}")
                    result['content'] = result['snippet']
                    
                results.append(result)
                
        except Exception as e:
            print(f"Search error: {e}")
            
        print(f"SearchAgent: Found {len(results)} results")
        return results
    
    def extract_content(self, url: str) -> str:
        """Extract the main content from a webpage."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=3)
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for element in soup(['script', 'style', 'header', 'footer', 'nav']):
                element.decompose()
                
            # Get text
            text = soup.get_text(separator=' ', strip=True)
            text = re.sub(r'\s+', ' ', text).strip()
            
            return text
        except Exception as e:
            return ""


class StorageAgent:
    """Agent responsible for storing and categorizing information."""
    
    def __init__(self):
        self.categories = ["healthcare", "technology", "sports", "business", 
                          "politics", "entertainment", "science", "education", "other"]
        self.model = genai.GenerativeModel('gemini-1.5-pro')
        
    def categorize(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Categorize the search results using Gemini."""
        print("StorageAgent: Categorizing results...")
        
        categorized_results = []
        
        for result in results:
            # Skip if there's no content
            if not result.get('title') and not result.get('snippet'):
                result['category'] = 'other'
                categorized_results.append(result)
                continue
                
            # Prepare text for categorization
            text_to_categorize = f"Title: {result['title']}\n"
            text_to_categorize += f"Content: {result['snippet']}"
            
            # Use Gemini to categorize
            prompt = f"""
            Categorize the following text into exactly ONE of these categories:
            healthcare, technology, sports, business, politics, entertainment, science, education, other.
            
            Text to categorize:
            {text_to_categorize}
            
            Response format: Just return the category name in lowercase, nothing else.
            """
            
            try:
                response = self.model.generate_content(prompt)
                category = response.text.strip().lower()
                
                # Validate the category
                if category not in self.categories:
                    category = "other"
                    
                result['category'] = category
                
            except Exception as e:
                print(f"Error during categorization: {e}")
                # Fallback to simple keyword matching
                result['category'] = self._simple_categorize(text_to_categorize)
                
            categorized_results.append(result)
            
        print("StorageAgent: Categorization complete")
        return categorized_results
    
    def _simple_categorize(self, text: str) -> str:
        """Simple fallback categorization method using keyword matching."""
        text = text.lower()
        
        # Simple keyword lists for each category
        keywords = {
            "healthcare": ["health", "medical", "doctor", "hospital", "patient", "disease", "treatment"],
            "technology": ["tech", "computer", "software", "digital", "app", "AI", "internet", "data"],
            "sports": ["sport", "team", "player", "game", "match", "tournament", "football", "basketball"],
            "business": ["business", "company", "market", "economy", "finance", "investment", "profit"],
            "politics": ["politics", "government", "election", "president", "policy", "law", "vote"],
            "entertainment": ["movie", "film", "music", "celebrity", "TV", "show", "star", "actor"],
            "science": ["science", "research", "study", "scientist", "discovery", "physics", "biology"],
            "education": ["education", "school", "university", "student", "teacher", "learning", "degree"]
        }
        
        # Count keyword matches for each category
        scores = {category: 0 for category in self.categories}
        
        for category, category_keywords in keywords.items():
            for keyword in category_keywords:
                scores[category] += text.count(keyword)
        
        # Get category with highest score
        max_score = max(scores.values())
        if max_score > 0:
            return max(scores.items(), key=lambda x: x[1])[0]
        
        return "other"
        
    def store_to_excel(self, results: List[Dict[str, Any]], filename: str = "search_results.xlsx") -> str:
        """Store the categorized results in an Excel file."""
        print(f"StorageAgent: Storing {len(results)} results to Excel...")
        
        # Prepare data for Excel
        data = []
        for result in results:
            data.append({
                'Title': result['title'],
                'URL': result['url'],
                'Snippet': result['snippet'][:500],  # Limit snippet size
                'Category': result['category']
            })
        
        # Create DataFrame
        df = pd.DataFrame(data)
        
        try:
            # Try to save as Excel
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                # Write all data to 'All Results' sheet
                df.to_excel(writer, sheet_name='All Results', index=False)
                
                # Write separate sheets for each category
                for category in self.categories:
                    category_df = df[df['Category'] == category]
                    if not category_df.empty:
                        category_df.to_excel(writer, sheet_name=category.capitalize(), index=False)
            
            print(f"StorageAgent: Data stored in {filename}")
            return filename
        except Exception as e:
            # Fallback to CSV
            print(f"Error saving to Excel: {e}")
            csv_filename = "search_results.csv"
            df.to_csv(csv_filename, index=False)
            print(f"StorageAgent: Data stored in {csv_filename}")
            return csv_filename


class SummaryAgent:
    """Agent responsible for summarizing information."""
    
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-1.5-pro')
    
    def summarize(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Summarize the search results using Gemini."""
        print("SummaryAgent: Generating summary...")
        
        # Gather data for summarization
        all_text = ""
        for result in results[:5]:  # Limit to top 5 results to avoid token limits
            all_text += f"Title: {result['title']}\n"
            all_text += f"Snippet: {result['snippet']}\n\n"
        
        # Count categories
        category_counts = {}
        for result in results:
            category = result['category']
            if category in category_counts:
                category_counts[category] += 1
            else:
                category_counts[category] = 1
                
        # Use Gemini to generate summary
        try:
            prompt = f"""
            Summarize the following search results in 3-4 paragraphs. 
            Focus on the main themes and key information.
            
            Search Results:
            {all_text}
            
            Your summary should be comprehensive but concise.
            """
            
            response = self.model.generate_content(prompt)
            summary_text = response.text.strip()
            
        except Exception as e:
            print(f"Error generating summary: {e}")
            summary_text = "Failed to generate summary. Please check the Excel file for detailed results."
        
        # Create summary object
        summary = {
            "total_results": len(results),
            "category_distribution": category_counts,
            "summary": summary_text
        }
        
        print("SummaryAgent: Summary generated")
        return summary
    
    def format_output(self, summary: Dict[str, Any], results: List[Dict[str, Any]], excel_path: str) -> str:
        """Format the summary and results into a readable output."""
        output = "# Search Results Summary\n\n"
        
        # Add summary statistics
        output += f"## Overview\n"
        output += f"- Total results found: {summary['total_results']}\n"
        output += f"- Results saved to: {excel_path}\n\n"
        
        # Add category distribution
        output += f"## Category Distribution\n"
        for category, count in summary['category_distribution'].items():
            percentage = (count / summary['total_results']) * 100
            output += f"- {category.capitalize()}: {count} ({percentage:.1f}%)\n"
        output += "\n"
        
        # Add summary text
        output += f"## Content Summary\n"
        output += summary['summary'] + "\n\n"
        
        # Add top result from each category
        output += f"## Top Result by Category\n"
        
        for category in summary['category_distribution'].keys():
            category_results = [r for r in results if r['category'] == category]
            if category_results:
                output += f"### {category.capitalize()}\n"
                # Show top result
                result = category_results[0]
                output += f"**{result['title']}**\n"
                output += f"{result['snippet'][:200]}...\n"
                output += f"[Source]({result['url']})\n\n"
        
        return output


class MultiAgentSystem:
    """Coordinator for the multi-agent system."""
    
    def __init__(self):
        self.search_agent = SearchAgent()
        self.storage_agent = StorageAgent()
        self.summary_agent = SummaryAgent()
        
    def process(self, query: str, max_results: int = 8) -> str:
        """Process a search query through all agents."""
        print(f"Starting multi-agent processing for query: '{query}'")
        
        # Step 1: Search for information
        results = self.search_agent.search(query, max_results)
        
        if not results:
            return "No results found. Please try a different query."
        
        # Step 2: Categorize and store information
        categorized_results = self.storage_agent.categorize(results)
        excel_path = self.storage_agent.store_to_excel(categorized_results)
        
        # Step 3: Summarize information
        summary = self.summary_agent.summarize(categorized_results)
        output = self.summary_agent.format_output(summary, categorized_results, excel_path)
        
        print("Multi-agent processing complete")
        return output


# Example usage
if __name__ == "__main__":
    # Make sure to set your API key before running
    if GOOGLE_API_KEY == "YOUR_GEMINI_API_KEY":
        print("Please set your Google Gemini API key first!")
    else:
        mas = MultiAgentSystem()
        query = input("Enter your search query: ")
        result = mas.process(query)
        print("\nFINAL OUTPUT:")
        print(result)