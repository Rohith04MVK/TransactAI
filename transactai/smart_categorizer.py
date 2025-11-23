import torch
import re
import json
from pathlib import Path
from datetime import datetime
from sentence_transformers import SentenceTransformer, util
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
from rich.console import Console
from rich.panel import Panel
from rich.progress import track

console = Console()

# Configuration defaults
EMBEDDING_MODEL = 'all-MiniLM-L6-v2'
LLM_MODEL_ID = "Qwen/Qwen2.5-1.5B-Instruct"
SIMILARITY_THRESHOLD = 0.55
DEDUPLICATION_THRESHOLD = 0.70
CONFIDENCE_FLOOR = 0.30  # Below this, always ask LLM

class SmartCategorizer:
    def __init__(self, data_dir="./categorizer_data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

        # Load AI models first
        with console.status("[bold green]Loading AI Models...[/bold green]"):
            self.embedder = SentenceTransformer(EMBEDDING_MODEL)
            self.tokenizer = AutoTokenizer.from_pretrained(LLM_MODEL_ID)
            self.llm = AutoModelForCausalLM.from_pretrained(
                LLM_MODEL_ID,
                torch_dtype=torch.float16,
                device_map="auto"
            )
            self.pipe = pipeline("text-generation", model=self.llm, tokenizer=self.tokenizer)

        # Try to restore previous state or initialize fresh
        if self._state_exists():
            console.print("[bold yellow]📂 Found existing data, restoring...[/bold yellow]")
            self._load_state()
        else:
            console.print("[bold cyan]✨ Initializing fresh knowledge base...[/bold cyan]")
            self._initialize_fresh()

        console.print(f"[bold cyan]✓ System Ready[/bold cyan] - {len(self.categories)} categories loaded\n")

    def _initialize_fresh(self):
        """Initialize with seed categories"""
        # Rich initial knowledge base with semantic variations
        self.category_seeds = {
            "Fast Food": ["mcdonalds", "kfc", "burger king", "pizza", "subway", "taco bell", "wendys", "dominos", "papa johns"],
            "Groceries": ["supermarket", "grocery", "walmart", "target", "whole foods", "trader joes", "costco", "kroger", "safeway", "fresh", "bazaar", "dmart", "reliance fresh", "big bazaar"],
            "Utilities": ["electric", "water", "gas", "internet", "phone", "mobile", "airtel", "jio", "vodafone", "vi", "bill", "postpaid", "broadband"],
            "Transportation": ["uber", "lyft", "taxi", "ola", "rapido", "fuel", "petrol", "gas station", "oil", "parking", "metro", "bus", "train"],
            "Entertainment": ["netflix", "spotify", "hulu", "prime video", "disney", "zee5", "hotstar", "bookmyshow", "movie", "theater", "concert", "gaming"],
            "Online Shopping": ["amazon", "ebay", "flipkart", "myntra", "ajio", "nykaa", "meesho", "online", "shopping"],
            "Food Delivery": ["ubereats", "doordash", "grubhub", "swiggy", "zomato", "delivery", "takeout"],
            "Rent": ["rent", "landlord", "lease", "housing", "apartment"],
            "Income": ["salary", "payroll", "wage", "deposit", "income", "payment received", "transfer from"],
            "Health": ["pharmacy", "doctor", "hospital", "clinic", "medical", "apollo", "health", "medicine"],
            "Travel": ["hotel", "airbnb", "oyo", "booking", "flight", "airline", "airfare", "treebo"],
            "Subscription": ["subscription", "monthly", "membership", "premium", "annual"]
        }

        # Flatten to create initial categories
        self.categories = list(self.category_seeds.keys())
        self.category_embeddings = self.embedder.encode(self.categories, convert_to_tensor=True)

        # Simple cache for exact matches
        self.cache = {}

        # Track corrections for learning
        self.corrections = []

        # Save initial state
        self._save_state()

    def _state_exists(self):
        """Check if saved state exists"""
        return (self.data_dir / 'embeddings.pt').exists() and (self.data_dir / 'state.json').exists()

    def _save_state(self):
        """Save all learned data to disk"""
        try:
            # Save embeddings and categories (binary format)
            torch.save({
                'category_embeddings': self.category_embeddings,
                'categories': self.categories
            }, self.data_dir / 'embeddings.pt')

            # Save human-readable data (JSON)
            with open(self.data_dir / 'state.json', 'w') as f:
                json.dump({
                    'cache': self.cache,
                    'corrections': self.corrections,
                    'category_seeds': self.category_seeds,
                    'last_updated': datetime.now().isoformat()
                }, f, indent=2)

        except Exception as e:
            console.print(f"[red]⚠️  Error saving state: {e}[/red]")

    def _load_state(self):
        """Restore previous session from disk"""
        try:
            # Load embeddings and categories
            data = torch.load(self.data_dir / 'embeddings.pt')
            self.category_embeddings = data['category_embeddings']
            self.categories = data['categories']

            # Load JSON state
            with open(self.data_dir / 'state.json', 'r') as f:
                state = json.load(f)
                self.cache = state['cache']
                self.corrections = state['corrections']
                self.category_seeds = state['category_seeds']

                last_updated = state.get('last_updated', 'Unknown')
                console.print(f"[dim]Last updated: {last_updated}[/dim]")

        except Exception as e:
            console.print(f"[red]⚠️  Error loading state: {e}[/red]")
            console.print("[yellow]Initializing fresh...[/yellow]")
            self._initialize_fresh()

    def reset_data(self):
        """Clear all saved data and start fresh"""
        import shutil
        if self.data_dir.exists():
            shutil.rmtree(self.data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self._initialize_fresh()
        console.print("[bold green]✓ Data reset complete[/bold green]")

    def _normalize_transaction(self, transaction):
        """Clean merchant names for better matching"""
        # Remove numbers, extra spaces, common suffixes
        cleaned = re.sub(r'[0-9#]+', '', transaction)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    def _ask_llm(self, transaction, existing_categories):
        """Ask LLM with rich context and better prompting"""

        prompt_text = (
            f"You are analyzing a bank transaction to categorize spending.\n\n"
            f"Available categories (use one of these if suitable):\n"
            f"{', '.join(existing_categories)}\n\n"
            f"Transaction: '{transaction}'\n\n"
            f"Instructions:\n"
            f"1. If this clearly fits an existing category, use that exact category name\n"
            f"2. If it doesn't fit well, create a NEW general category that:\n"
            f"   - Is broad enough to include similar future transactions\n"
            f"   - Uses 1-3 words (e.g., 'Electronics', 'Pet Care', 'Home Improvement')\n"
            f"   - Is NOT too specific (Bad: 'Amazon Prime', Good: 'Online Shopping' or 'Entertainment')\n\n"
            f"Examples:\n"
            f"- 'AMAZON DIGITAL SVCS' → Entertainment (streaming) or Online Shopping\n"
            f"- 'PETCO 5512' → Pet Care\n"
            f"- 'HOME DEPOT 8821' → Home Improvement\n"
            f"- 'STARBUCKS 447' → Coffee Shops or Food & Drink\n\n"
            f"Reply with ONLY the category name (1-3 words, no explanation):"
        )

        messages = [
            {"role": "system", "content": "You are a financial transaction classifier. Be specific enough to be useful but general enough to reuse. Output ONLY the category name."},
            {"role": "user", "content": prompt_text}
        ]

        prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        outputs = self.pipe(prompt, max_new_tokens=20, do_sample=True, temperature=0.3, top_p=0.9)

        generated = outputs[0]["generated_text"]
        category = generated.split("<|im_start|>assistant")[-1].strip()
        category = category.replace("<|im_end|>", "").strip()

        # Extract just the category name (remove any explanation)
        category = category.split('\n')[0].split('.')[0].strip().title()

        # Clean up any weird LLM outputs
        category = re.sub(r'[^\w\s&]', '', category).strip()

        # If output is too long or weird, default
        if len(category) > 30 or not category:
            category = "Miscellaneous"

        return category

    def _update_embeddings(self, new_category):
        """Add new category to vector index"""
        new_emb = self.embedder.encode(new_category, convert_to_tensor=True)
        self.category_embeddings = torch.cat((self.category_embeddings, new_emb.unsqueeze(0)), 0)
        self.categories.append(new_category)
        self._save_state()  # Persist new category

    def _check_keyword_rules(self, transaction):
        """Enhanced keyword matching using seed knowledge"""
        tx_lower = transaction.lower()

        # Check against all seed keywords
        for category, keywords in self.category_seeds.items():
            if any(keyword in tx_lower for keyword in keywords):
                return category

        return None

    def process(self, transaction):
        """Enhanced processing pipeline with multiple intelligence layers"""

        # Normalize input
        normalized = self._normalize_transaction(transaction)

        # Layer 1: Check cache for exact matches
        if transaction in self.cache:
            return {
                "transaction": transaction,
                "category": self.cache[transaction],
                "confidence": 1.0,
                "source": "Cache",
                "action": "Cached"
            }

        # Layer 2: Keyword rules (instant classification)
        rule_match = self._check_keyword_rules(transaction)
        if rule_match:
            self.cache[transaction] = rule_match
            return {
                "transaction": transaction,
                "category": rule_match,
                "confidence": 1.0,
                "source": "Rule",
                "action": "Rule Match"
            }

        # Layer 3: Vector similarity search
        tx_embedding = self.embedder.encode(normalized, convert_to_tensor=True)
        scores = util.cos_sim(tx_embedding, self.category_embeddings)[0]
        best_idx = scores.argmax().item()
        best_score = scores[best_idx].item()
        best_match = self.categories[best_idx]

        # High confidence match
        if best_score >= SIMILARITY_THRESHOLD:
            self.cache[transaction] = best_match
            return {
                "transaction": transaction,
                "category": best_match,
                "confidence": best_score,
                "source": "Vector DB",
                "action": "Existing"
            }

        # Layer 4: LLM for low confidence cases
        console.print(f"[yellow]    >> Low confidence ({best_score:.2f}). Consulting AI...[/yellow]")
        suggested_category = self._ask_llm(normalized, self.categories)

        # Layer 5: Deduplication check
        sugg_embedding = self.embedder.encode(suggested_category, convert_to_tensor=True)
        check_scores = util.cos_sim(sugg_embedding, self.category_embeddings)[0]
        dupe_idx = check_scores.argmax().item()
        dupe_score = check_scores[dupe_idx].item()

        if dupe_score >= DEDUPLICATION_THRESHOLD:
            # Map to existing similar category
            final_category = self.categories[dupe_idx]
            action = f"Mapped '{suggested_category}' → {final_category}"
        else:
            # Truly new category
            self._update_embeddings(suggested_category)
            final_category = suggested_category
            action = "✨ Created New"

        self.cache[transaction] = final_category
        self._save_state()  # Persist changes

        return {
            "transaction": transaction,
            "category": final_category,
            "confidence": dupe_score if dupe_score >= DEDUPLICATION_THRESHOLD else 0.95,
            "source": "LLM (Qwen)",
            "action": action
        }

    def batch_process(self, transactions):
        """Process multiple transactions efficiently"""
        results = []
        for tx in track(transactions, description="Processing transactions..."):
            results.append(self.process(tx))
        return results

    def correct(self, transaction, correct_category):
        """Manual correction - adds to learning history"""
        self.cache[transaction] = correct_category
        self.corrections.append((transaction, correct_category))

        # If category doesn't exist, add it
        if correct_category not in self.categories:
            self._update_embeddings(correct_category)
        else:
            self._save_state()  # Save the correction

        console.print(f"[green]✓ Learned:[/green] '{transaction}' → {correct_category}")

    def show_stats(self):
        """Display system statistics"""
        # Calculate storage size
        storage_size = 0
        if self.data_dir.exists():
            for file in self.data_dir.glob('*'):
                storage_size += file.stat().st_size
        storage_mb = storage_size / (1024 * 1024)

        panel = Panel(
            f"[cyan]Total Categories:[/cyan] {len(self.categories)}\n"
            f"[cyan]Cached Transactions:[/cyan] {len(self.cache)}\n"
            f"[cyan]Manual Corrections:[/cyan] {len(self.corrections)}\n"
            f"[cyan]Storage Used:[/cyan] {storage_mb:.2f} MB\n"
            f"[cyan]Data Directory:[/cyan] {self.data_dir.absolute()}",
            title="System Stats",
            border_style="blue"
        )
        console.print(panel)
