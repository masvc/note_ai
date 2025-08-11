#!/usr/bin/env python3
"""
Peaky Media記事まとめ自動生成システム（プロダクトリサーチ限定版）
https://peaky.co.jp/feed/ からProduct Researchカテゴリのみを取得し、AIプロダクトまとめ記事を生成
"""

import os
import asyncio
import feedparser
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
import re
import json
from typing import List, Dict
import html

# 環境変数読み込み
load_dotenv()

class PeakyArticleGenerator:
    def __init__(self):
        self.anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
        if not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY環境変数を設定してください")
        
        self.peaky_feed_url = "https://peaky.co.jp/feed/"
        self.output_dir = "articles"
        
        # 出力ディレクトリを作成
        os.makedirs(self.output_dir, exist_ok=True)
    
    def fetch_peaky_articles(self) -> List[Dict]:
        """Peaky MediaのRSSフィードからProduct Research記事のみを取得"""
        print("📡 Peaky MediaのRSSフィードを取得中...")
        
        try:
            # RSSフィードを取得
            feed = feedparser.parse(self.peaky_feed_url)
            
            if feed.bozo:
                print("⚠️ RSSフィードの解析でエラーが発生しましたが続行します")
            
            all_articles = []
            product_research_articles = []
            
            for entry in feed.entries:
                # 記事情報を抽出
                article = {
                    'title': entry.title,
                    'link': entry.link,
                    'summary': self._clean_html_content(getattr(entry, 'summary', '')),
                    'published': getattr(entry, 'published', ''),
                    'tags': [tag.term for tag in getattr(entry, 'tags', [])],
                    'category': getattr(entry, 'category', ''),
                    'content': self._extract_content(entry)
                }
                
                all_articles.append(article)
                
                # Product Researchカテゴリかどうかを判定
                if self._is_product_research(entry):
                    product_research_articles.append(article)
            
            print(f"✅ Product Research記事: {len(product_research_articles)}件を取得")
            print(f"📊 フィード全体: {len(all_articles)}件中 {len(product_research_articles)}件を選別")
            
            # カテゴリ別の内訳を表示
            category_counts = {}
            for article in all_articles:
                cat = article['category'] or 'その他'
                category_counts[cat] = category_counts.get(cat, 0) + 1
            
            print("📋 カテゴリ別内訳:")
            for cat, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
                mark = "✅" if cat == "Product Research" else "❌"
                print(f"  {mark} {cat}: {count}件")
            
            return product_research_articles
            
        except Exception as e:
            print(f"❌ RSSフィード取得エラー: {e}")
            return []
    
    def _is_product_research(self, entry) -> bool:
        """Product Researchカテゴリの記事かどうかを判定"""
        # 方法1: category属性で判定（最も確実）
        if hasattr(entry, 'category') and entry.category == 'Product Research':
            return True
        
        # 方法2: tagsで判定（フォールバック）
        if hasattr(entry, 'tags'):
            for tag in entry.tags:
                if tag.term == 'Product Research':
                    return True
        
        return False
    
    def _clean_html_content(self, content: str) -> str:
        """HTMLタグを除去してクリーンなテキストにする"""
        if not content:
            return ""
        
        # HTMLエンティティをデコード
        content = html.unescape(content)
        
        # HTMLタグを除去
        content = re.sub(r'<[^>]+>', '', content)
        
        # 余分な空白文字を除去
        content = re.sub(r'\s+', ' ', content)
        content = content.strip()
        
        return content
    
    def _extract_content(self, entry) -> str:
        """記事の本文内容を抽出"""
        content = ""
        if hasattr(entry, 'content'):
            content = entry.content[0].value if entry.content else ''
        elif hasattr(entry, 'summary'):
            content = entry.summary
        
        # HTMLタグをクリーンアップ
        return self._clean_html_content(content)
    
    def select_top_articles(self, articles: List[Dict], count: int = 5) -> List[Dict]:
        """人気・関連性の高いプロダクト記事を選別"""
        print(f"🔍 上位{count}プロダクト記事を選別中...")
        print("⚡ スコアリング基準: 話題性・プロダクト魅力度・新しさ・記事充実度")
        
        # スコアリング関数（プロダクトリサーチ専用）
        def score_article(article: Dict) -> float:
            score = 0
            
            # プロダクトの魅力度（特定キーワードでボーナス）
            high_impact_keywords = [
                'AI', '自動化', '効率化', '革新的', '画期的', '次世代',
                'リリース', '発表', '最新', '無料', 'オープンソース',
                'ノーコード', 'ローコード', 'ブラウザベース', 'API'
            ]
            
            for keyword in high_impact_keywords:
                if keyword in article['title']:
                    score += 2
            
            # プロダクト関連の重要キーワード
            product_priority_keywords = [
                'ツール', 'プラットフォーム', 'サービス', 'アプリ', 
                'ソフトウェア', 'SaaS', 'ダッシュボード', 'エディタ',
                'ジェネレーター', 'ビルダー', 'クリエイター'
            ]
            
            for keyword in product_priority_keywords:
                if keyword in article['title'] or keyword in article['summary']:
                    score += 1.5
            
            # 技術分野の多様性ボーナス
            tech_categories = [
                'AI', 'Web開発', 'モバイル', 'デザイン', 'マーケティング',
                'セキュリティ', 'データ分析', '業務効率化', 'コミュニケーション'
            ]
            
            for category in tech_categories:
                if category in article['title'] or category in ' '.join(article['tags']):
                    score += 1
            
            # 記事の新しさ（最近の記事を優遇）
            try:
                if article['published']:
                    pub_date = datetime.strptime(article['published'][:19], '%Y-%m-%dT%H:%M:%S')
                    days_ago = (datetime.now() - pub_date).days
                    if days_ago <= 1:
                        score += 5  # 今日・昨日の記事は高得点
                    elif days_ago <= 7:
                        score += 3
                    elif days_ago <= 30:
                        score += 1
            except:
                pass
            
            # 要約の充実度
            if len(article['summary']) > 100:
                score += 1
            
            return score
        
        # スコア順でソート
        scored_articles = [(article, score_article(article)) for article in articles]
        scored_articles.sort(key=lambda x: x[1], reverse=True)
        
        selected = [article for article, score in scored_articles[:count]]
        
        print(f"✅ 選別完了:")
        for i, (article, score) in enumerate(scored_articles[:count], 1):
            print(f"  {i}. {article['title'][:60]}... (スコア: {score:.1f})")
        
        return selected
    
    def _extract_keyword_from_articles(self, selected_articles: List[Dict]) -> str:
        """記事からアイキャッチ検索に適したキーワードを抽出"""
        # アイキャッチ検索に適した一般的なキーワード候補
        keyword_candidates = []
        
        # 技術系キーワード
        tech_keywords = ['AI', '自動化', '音声', '画像', 'デザイン', '開発', 'コード', 'IT', 'エンジニア']
        # 一般系キーワード  
        general_keywords = ['効率', '便利', '無料', '簡単', '革新', '未来', '作業効率化', 'アプリ', 'ゲーム']
        # 感情系キーワード
        emotion_keywords = ['驚き', '楽しい', '安心', '便利', '快適']
        
        all_text = ""
        for article in selected_articles:
            all_text += f"{article['title']} {article['summary']} {' '.join(article['tags'])}"
        
        all_text = all_text.lower()
        
        # 各カテゴリからマッチするキーワードを収集
        for keyword in tech_keywords + general_keywords + emotion_keywords:
            if keyword.lower() in all_text:
                keyword_candidates.append(keyword)
        
        # マッチしない場合のフォールバック
        if not keyword_candidates:
            keyword_candidates = ['AI', 'ツール', '便利', '効率', '未来']
        
        # ランダムに選択
        import random
        return random.choice(keyword_candidates)
    
    def _generate_article_title(self, selected_articles: List[Dict], keyword: str) -> str:
        """魅力的で具体的なタイトルを生成"""
        import random
        
        # 記事の特徴を分析
        has_ai = any('AI' in article['title'] or 'ai' in article['title'].lower() for article in selected_articles)
        has_automation = any('自動' in article['title'] or 'automation' in article['title'].lower() for article in selected_articles)
        has_design = any('デザイン' in article['title'] or 'design' in article['title'].lower() for article in selected_articles)
        has_dev_tools = any('開発' in article['title'] or '開発者' in ' '.join(article['tags']) for article in selected_articles)
        
        # 特徴に応じたタイトルパターン
        if has_ai:
            title_patterns = [
                f"AIで作業効率爆上がりプロダクト{len(selected_articles)}選",
                f"話題のAIツール{len(selected_articles)}選で生産性アップ",
                f"エンジニア注目のAIプロダクト{len(selected_articles)}選",
                f"最新AI技術を活用したプロダクト{len(selected_articles)}選"
            ]
        elif has_automation:
            title_patterns = [
                f"自動化で楽になる便利プロダクト{len(selected_articles)}選",
                f"作業効率化の救世主プロダクト{len(selected_articles)}選",
                f"時短・自動化プロダクト{len(selected_articles)}選",
                f"面倒な作業を自動化するプロダクト{len(selected_articles)}選"
            ]
        elif has_design:
            title_patterns = [
                f"デザイナー必見の最新ツール{len(selected_articles)}選",
                f"クリエイター向け便利プロダクト{len(selected_articles)}選",
                f"デザイン作業が捗るプロダクト{len(selected_articles)}選",
                f"美しいデザインを作るプロダクト{len(selected_articles)}選"
            ]
        elif has_dev_tools:
            title_patterns = [
                f"開発者の生産性を上げるプロダクト{len(selected_articles)}選",
                f"エンジニア必見の開発ツール{len(selected_articles)}選",
                f"コーディングが楽になるプロダクト{len(selected_articles)}選",
                f"開発効率化プロダクト{len(selected_articles)}選"
            ]
        else:
            # 汎用パターン
            title_patterns = [
                f"今週バズってる注目プロダクト{len(selected_articles)}選",
                f"エンジニアが選ぶ便利プロダクト{len(selected_articles)}選",
                f"話題沸騰中のプロダクト{len(selected_articles)}選",
                f"使ってみたくなるプロダクト{len(selected_articles)}選",
                f"革新的なプロダクト{len(selected_articles)}選をご紹介",
                f"注目度急上昇のプロダクト{len(selected_articles)}選"
            ]
        
        main_title = random.choice(title_patterns)
        return f"5分で読める、{main_title} 【今日のキーワード：「{keyword}」】"
    
    def _generate_keyword_blockquote(self, keyword: str, selected_articles: List[Dict]) -> str:
        """キーワードに関するポジティブな感想を生成"""
        import random
        
        # キーワード別の感想パターン
        keyword_comments = {
            'AI': [
                "最近のAI技術の進歩って本当に目を見張るものがありますよね。こんなにワクワクする時代に生きていることに感謝です！",
                "AI分野の革新スピードがもう止まらないですね。毎日新しいプロダクトが出てきて、未来がどんどん現実になっていく感じがたまりません！",
                "AIがここまで身近になるなんて、数年前は想像もできませんでした。技術の力で世界がより良くなっていく瞬間を目の当たりにしている気分です！"
            ],
            '自動化': [
                "自動化技術の進歩で、みんながもっとクリエイティブな仕事に集中できるようになってきましたね。テクノロジーの力ってすごい！",
                "面倒な作業を自動化してくれるツールがどんどん出てきて、本当に助かります。生産性向上に直結する素晴らしい時代ですね！",
                "自動化によって人間はより人間らしい仕事に専念できる。これこそテクノロジーが目指すべき方向だと思います！"
            ],
            '音声': [
                "音声技術の進歩が本当にすごくて、もう人間の声と区別がつかないレベルになってきましたね。技術の進歩にワクワクが止まりません！",
                "音声インターフェースがこれほど自然になるとは！未来のコミュニケーション形態が現実になっている感じがします。",
                "音声合成技術の発達で、新しい表現の可能性が無限に広がっていますね。クリエイティブな領域での活用が楽しみです！"
            ],
            'デザイン': [
                "デザインツールの進化が止まらないですね！誰でもプロ級のデザインができる時代になって、可能性が無限大に感じます。",
                "美しいデザインを簡単に作れるツールがどんどん登場して、創作活動のハードルがグッと下がりましたね。素晴らしい時代です！",
                "デザインとテクノロジーの融合が生み出すイノベーションに、いつもワクワクさせられます。未来はもっと美しくなりそう！"
            ],
            '開発': [
                "開発ツールの進歩のおかげで、作業の生産性がどんどん向上していますね。新しいアイデアを形にするのがより楽しくなっています！",
                "開発環境がこれほど便利になるなんて本当にすごいです。素晴らしいツールを作ってくれる開発者の皆さんに感謝です！",
                "新しい開発ツールが出るたびに、「もっと早く出会いたかった！」と思ってしまいます。技術の進歩って本当に素晴らしい！"
            ],
            'ツール': [
                "便利なツールがこれだけたくさん出てくると、選ぶのも楽しい悩みですね。こんなに恵まれた環境にいることに感謝です！",
                "新しいツールとの出会いっていつもワクワクしますよね。生産性向上だけでなく、新しい発見もあって最高です！",
                "革新的なツールが次々と登場する現代って、本当に幸せな時代だと思います。可能性が無限大ですね！"
            ]
        }
        
        # デフォルトのポジティブコメント
        default_comments = [
            "テクノロジーの進歩のスピードに毎日驚かされています。こんなにエキサイティングな時代に生きていることが嬉しいです！",
            "新しいプロダクトとの出会いは、いつも新しい可能性を感じさせてくれますね。イノベーションの力ってすごい！",
            "革新的なプロダクトが次々と生まれる現代って、本当に素晴らしい時代だと思います。未来への期待が膨らみます！"
        ]
        
        # キーワードに対応するコメントを取得、なければデフォルト
        comments = keyword_comments.get(keyword, default_comments)
        return random.choice(comments)
    
    def _extract_product_tags(self, selected_articles: List[Dict]) -> List[str]:
        """プロダクト固有名からハッシュタグを抽出"""
        product_tags = []
        
        for article in selected_articles:
            title = article['title']
            
            # プロダクト名を抽出（– または - より前の部分）
            product_name = re.split(r'[–\-]', title)[0].strip()
            
            # スペースを除去してタグ化
            clean_name = re.sub(r'[^\w\d]', '', product_name)
            if len(clean_name) > 2:  # 3文字以上のもののみ
                product_tags.append(f"#{clean_name}")
        
        return product_tags

    async def _generate_all_content_with_claude(self, selected_articles: List[Dict]) -> Dict[str, str]:
        """Claude APIで全コンテンツを統合生成（効率化版）"""
        print("🤖 Claude APIで統合コンテンツ生成中...")
        
        # 記事情報をまとめる
        articles_info = []
        for i, article in enumerate(selected_articles, 1):
            articles_info.append(f"""
記事{i}:
タイトル: {article['title']}
要約: {article['summary'][:200]}...
タグ: {', '.join(article['tags'][:5])}
""")
        
        unified_prompt = f"""
以下の{len(selected_articles)}つのプロダクト記事を分析して、Note.com記事に必要な要素を生成してください。

記事情報:
{''.join(articles_info)}

以下の4つの要素を生成してください：

1. **アイキャッチキーワード**: Note.comで新しくて質の高い画像が見つかりやすい1語
2. **blockquoteコメント**: キーワードに関するポジティブで親しみやすい感想（1-2行）
3. **記事タイトル**: 「5分で読める、[魅力的な内容]{len(selected_articles)}選 【今日のキーワード：「[キーワード]」】」形式
4. **ハッシュタグ**: プロダクト名から生成した適切なハッシュタグ（最大5個）

出力形式（必須）:
```
キーワード: [1語のキーワード]
blockquote: [親しみやすいコメント文]
タイトル: [完整なタイトル]
ハッシュタグ: #tag1 #tag2 #tag3 #tag4 #tag5
```

注意事項:
- キーワードはNote.comで頻繁に更新される分野から選択
- blockquoteはエンジニア用語を避けて一般読者向けに
- ハッシュタグは英数字のみ、3文字以上
- すべて今回の記事内容に関連させる
"""

        try:
            response = await self._call_claude_api_for_content(unified_prompt, max_tokens=800)
            
            if response:
                parsed_content = self._parse_unified_response(response, selected_articles)
                if parsed_content:
                    print("✅ Claude統合生成完了")
                    return parsed_content
            
            print("⚠️ Claude API統合生成失敗、個別生成にフォールバック")
            return await self._generate_individual_content(selected_articles)
            
        except Exception as e:
            print(f"❌ Claude API統合生成エラー: {e}")
            return await self._generate_individual_content(selected_articles)

    def _parse_unified_response(self, response: str, selected_articles: List[Dict]) -> Dict[str, str]:
        """統合レスポンスを解析"""
        try:
            result = {}
            
            # キーワード抽出
            keyword_match = re.search(r'キーワード[:\s]*([^\n\r]+)', response)
            if keyword_match:
                result['keyword'] = keyword_match.group(1).strip()
            
            # blockquote抽出
            blockquote_match = re.search(r'blockquote[:\s]*([^\n\r]+(?:\n[^#\n]*)*)', response, re.MULTILINE)
            if blockquote_match:
                result['blockquote'] = blockquote_match.group(1).strip()
            
            # タイトル抽出
            title_match = re.search(r'タイトル[:\s]*([^\n\r]+)', response)
            if title_match:
                result['title'] = title_match.group(1).strip()
            
            # ハッシュタグ抽出
            hashtag_match = re.search(r'ハッシュタグ[:\s]*([^\n\r]+)', response)
            if hashtag_match:
                hashtags_line = hashtag_match.group(1).strip()
                hashtags = re.findall(r'#\w+', hashtags_line)
                result['hashtags'] = hashtags
            
            # 必須要素が揃っているかチェック
            required_keys = ['keyword', 'blockquote', 'title']
            if all(key in result for key in required_keys):
                return result
            else:
                print(f"⚠️ 必須要素不足: {[k for k in required_keys if k not in result]}")
                return None
                
        except Exception as e:
            print(f"⚠️ 統合レスポンス解析エラー: {e}")
            return None

    async def _generate_individual_content(self, selected_articles: List[Dict]) -> Dict[str, str]:
        """個別生成フォールバック"""
        print("🔄 個別コンテンツ生成にフォールバック...")
        
        # 改良版キーワード抽出を使用
        keyword = await self._extract_keyword_from_articles_note_optimized(selected_articles)
        blockquote = self._generate_keyword_blockquote(keyword, selected_articles)
        hashtags = self._extract_product_tags(selected_articles)
        title = self._generate_article_title(selected_articles, keyword)
        
        return {
            'keyword': keyword,
            'blockquote': blockquote, 
            'title': title,
            'hashtags': hashtags
        }

    async def _extract_keyword_from_articles_note_optimized(self, selected_articles: List[Dict]) -> str:
        """Note.com最適化キーワード抽出（改良版）"""
        print("🎯 Note.com最適化キーワード抽出中...")
        
        # 記事内容を分析
        all_text = ""
        for article in selected_articles:
            all_text += f"{article['title']} {article['summary']} {' '.join(article['tags'])}"
        
        all_text_lower = all_text.lower()
        
        # Note.com最適化キーワード（確実に良い画像があるもの）
        priority_keywords = {
            'AI': ['ai', 'artificial intelligence', '人工知能'],
            'スタートアップ': ['startup', 'スタートアップ', '起業'],
            'ビジネス': ['business', 'ビジネス', '事業'],
            'デザイン': ['design', 'デザイン', 'ui', 'ux'],
            'テクノロジー': ['technology', 'tech', 'テクノロジー', '技術'],
            'イノベーション': ['innovation', 'イノベーション', '革新'],
            'プロダクト': ['product', 'プロダクト', 'ツール', 'tool'],
            'ワークスタイル': ['work', 'リモート', 'remote', '働き方'],
            'DX': ['dx', 'デジタル', 'digital', '変革'],
            'クリエイティブ': ['creative', 'クリエイティブ', 'アート']
        }
        
        # マッチングスコア計算
        keyword_scores = {}
        for keyword, patterns in priority_keywords.items():
            score = 0
            for pattern in patterns:
                score += all_text_lower.count(pattern.lower())
            if score > 0:
                keyword_scores[keyword] = score
        
        # プロダクト特化の場合の特別ルール
        product_indicators = ['ツール', 'アプリ', 'サービス', 'プラットフォーム', 'ソフトウェア']
        has_product_focus = any(indicator in all_text for indicator in product_indicators)
        
        if has_product_focus:
            product_specific_keywords = ['プロダクト', 'ツール', 'アプリケーション', 'ソフトウェア']
            for keyword in product_specific_keywords:
                if keyword in all_text:
                    keyword_scores[keyword] = keyword_scores.get(keyword, 0) + 3  # ボーナス
        
        # 最高スコアのキーワードを選択
        if keyword_scores:
            best_keyword = max(keyword_scores, key=keyword_scores.get)
            print(f"🎯 Note最適化選択: 「{best_keyword}」(スコア: {keyword_scores[best_keyword]})")
            return best_keyword
        
        # 最終フォールバック
        safe_keywords = ['ビジネス', 'テクノロジー', 'イノベーション', 'プロダクト', 'デザイン']
        import random
        selected = random.choice(safe_keywords)
        print(f"🎯 安全なフォールバック: 「{selected}」")
        return selected
    
    async def generate_article_with_claude(self, selected_articles: List[Dict]) -> str:
        """Claude APIを使って記事を生成（統合コンテンツ生成対応）"""
        print("🤖 Claude APIで記事生成中...")
        
        # 統合コンテンツ生成を試行
        content_elements = await self._generate_all_content_with_claude(selected_articles)
        
        if not content_elements:
            print("⚠️ 統合コンテンツ生成失敗、従来方式でフォールバック")
            return await self._generate_article_traditional(selected_articles)
        
        # 統合生成された要素を使用
        keyword = content_elements['keyword']
        blockquote = content_elements['blockquote']
        title = content_elements['title']
        hashtags = content_elements.get('hashtags', [])
        
        print(f"🎯 統合生成されたキーワード: 「{keyword}」")
        
        # プロンプトを構築
        articles_info = []
        for i, article in enumerate(selected_articles, 1):
            articles_info.append(f"""
記事{i}:
タイトル: {article['title']}
URL: {article['link']}
要約: {article['summary'][:200]}...
タグ: {', '.join(article['tags'][:5])}
""")
        
        prompt = f"""
以下のPeaky Mediaのプロダクトリサーチ記事を参考に、Note.com向けの親しみやすいプロダクトまとめ記事を作成してください。

参考記事（全てProduct Researchカテゴリ）:
{''.join(articles_info)}

作成する記事の要件:
1. タイトル: 「{title}」（既に決定済み）
2. キーワードblockquote: 「{blockquote}」（既に決定済み）
3. 導入部: 気軽で親しみやすい導入文（100-150文字程度）
4. 各プロダクト紹介: {len(selected_articles)}つのプロダクトを200-350文字で親しみやすく紹介
5. Peaky Mediaリンク: 「公式メディアで、毎日プロダクトリサーチを更新しています！お気軽にチェックしてみてください⬇︎」でURL単体配置
6. 親しみやすい結び: 読者との距離感を縮める呼びかけ
7. ハッシュタグ: {', '.join(hashtags)} + プロダクト関連タグ

文体の特徴:
- 親しみやすく話しかけるような文体
- 「これは便利そう！」「試してみたくなる」という表現
- 専門用語を避け、一般の方にも分かりやすく
- Note読者層に合わせた温かみのある表現
- プロダクトの魅力を分かりやすく伝える

リンクの埋め込み方（重要）:
- 詳細記事: URL単体で配置（Note.comが自動でプレビューカードを表示）
- Peaky Media: 「https://peaky.co.jp/」（URL単体で配置）
※マークダウンリンクは使わず、URL単体で配置してください
※「詳しくはこちら：」などの余分なテキストは不要です

記事構成:
# {title}

> {blockquote}

親しみやすい導入文

## 1. プロダクト名
紹介文

URL

...（{len(selected_articles)}つ繰り返し）

## 最後に
親しみやすい結び + 「公式メディアで、毎日プロダクトリサーチを更新しています！お気軽にチェックしてみてください⬇︎」 + Peaky MediaのURL単体配置
ハッシュタグ

Markdownフォーマットで出力してください。
"""

        try:
            # Claude APIに送信
            response = await self._call_claude_api(prompt)
            
            if response:
                print("✅ Claude APIで記事生成完了")
                return response
            else:
                return self._generate_fallback_article(selected_articles)
                
        except Exception as e:
            print(f"❌ Claude API呼び出しエラー: {e}")
            return self._generate_fallback_article(selected_articles)

    async def _generate_article_traditional(self, selected_articles: List[Dict]) -> str:
        """従来方式での記事生成（フォールバック用）"""
        print("🔄 従来方式で記事生成中...")
        
        # キーワードを抽出
        keyword = self._extract_keyword_from_articles(selected_articles)
        print(f"🎯 抽出されたキーワード: 「{keyword}」")
        
        # プロンプトを構築
        articles_info = []
        for i, article in enumerate(selected_articles, 1):
            articles_info.append(f"""
記事{i}:
タイトル: {article['title']}
URL: {article['link']}
要約: {article['summary'][:200]}...
タグ: {', '.join(article['tags'][:5])}
""")
        
        prompt = f"""
以下のPeaky Mediaのプロダクトリサーチ記事を参考に、Note.com向けの親しみやすいプロダクトまとめ記事を作成してください。

参考記事（全てProduct Researchカテゴリ）:
{''.join(articles_info)}

作成する記事の要件:
1. タイトル: 「5分で読める、[具体的で魅力的な内容] 【今日のキーワード：「{keyword}」】」の形式
2. キーワードblockquote: 記事冒頭に「{keyword}」について、テクノロジーやスタートアップが好きなポジティブな人の視点からの1-2行コメント
3. 導入部: 気軽で親しみやすい導入文（100-150文字程度）
4. 各プロダクト紹介: {len(selected_articles)}つのプロダクトを200-350文字で親しみやすく紹介
5. Peaky Mediaリンク: 「公式メディアで、毎日プロダクトリサーチを更新しています！お気軽にチェックしてみてください⬇︎」でURL単体配置
6. 親しみやすい結び: 読者との距離感を縮める呼びかけ
7. ハッシュタグ: プロダクト名 + プロダクト関連タグ

文体の特徴:
- 親しみやすく話しかけるような文体
- 「これは便利そう！」「試してみたくなる」という表現
- 専門用語を避け、一般の方にも分かりやすく
- Note読者層に合わせた温かみのある表現
- プロダクトの魅力を分かりやすく伝える

リンクの埋め込み方（重要）:
- 詳細記事: URL単体で配置（Note.comが自動でプレビューカードを表示）
- Peaky Media: 「https://peaky.co.jp/」（URL単体で配置）
※マークダウンリンクは使わず、URL単体で配置してください
※「詳しくはこちら：」などの余分なテキストは不要です

記事構成:
# 5分で読める、[具体的で魅力的なタイトル] 【今日のキーワード：「{keyword}」】

> キーワード「{keyword}」についてのポジティブなコメント（1-2行、エンジニア表現は避ける）

親しみやすい導入文

## 1. プロダクト名
紹介文

URL

...（{len(selected_articles)}つ繰り返し）

## 最後に
親しみやすい結び + 「公式メディアで、毎日プロダクトリサーチを更新しています！お気軽にチェックしてみてください⬇︎」 + Peaky MediaのURL単体配置
ハッシュタグ

Markdownフォーマットで出力してください。
"""

        try:
            # Claude APIに送信
            response = await self._call_claude_api(prompt)
            
            if response:
                print("✅ 従来方式で記事生成完了")
                return response
            else:
                return self._generate_fallback_article(selected_articles)
                
        except Exception as e:
            print(f"❌ 従来方式API呼び出しエラー: {e}")
            return self._generate_fallback_article(selected_articles)
    
    async def _call_claude_api(self, prompt: str) -> str:
        """Claude APIを呼び出し"""
        url = "https://api.anthropic.com/v1/messages"
        
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.anthropic_api_key,
            "anthropic-version": "2023-06-01"
        }
        
        data = {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 2000,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            if response.status_code == 401:
                print("❌ 認証エラー: APIキーが無効です")
                return None
            elif response.status_code == 404:
                print("❌ エンドポイントが見つかりません")
                return None
            
            response.raise_for_status()
            result = response.json()
            return result['content'][0]['text']
            
        except requests.exceptions.RequestException as e:
            print(f"❌ API通信エラー: {e}")
            return None
        except (KeyError, IndexError) as e:
            print(f"❌ APIレスポンス解析エラー: {e}")
            return None

    async def _call_claude_api_for_content(self, prompt: str, max_tokens: int = 800) -> str:
        """統合コンテンツ生成用のClaude API呼び出し"""
        url = "https://api.anthropic.com/v1/messages"
        
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.anthropic_api_key,
            "anthropic-version": "2023-06-01"
        }
        
        data = {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            if response.status_code == 401:
                print("❌ 認証エラー: APIキーが無効です")
                return None
            elif response.status_code == 404:
                print("❌ エンドポイントが見つかりません")
                return None
            
            response.raise_for_status()
            result = response.json()
            return result['content'][0]['text']
            
        except requests.exceptions.RequestException as e:
            print(f"❌ API通信エラー: {e}")
            return None
        except (KeyError, IndexError) as e:
            print(f"❌ APIレスポンス解析エラー: {e}")
            return None
    
    def _generate_fallback_article(self, selected_articles: List[Dict]) -> str:
        """プロダクトリサーチ専用の親しみやすい記事テンプレート"""
        print("📝 プロダクト専用記事を生成中...")
        
        # キーワードを抽出
        keyword = self._extract_keyword_from_articles(selected_articles)
        print(f"🎯 抽出されたキーワード: 「{keyword}」")
        
        # タイトルとblockquoteを生成
        article_title = self._generate_article_title(selected_articles, keyword)
        keyword_comment = self._generate_keyword_blockquote(keyword, selected_articles)
        product_tags = self._extract_product_tags(selected_articles)
        
        article_content = f"""# {article_title}

> {keyword_comment}

こんにちは！今回は最近見つけた面白いプロダクトを{len(selected_articles)}つご紹介します。

どれも「これは便利そう！」と思えるツールばかりで、日々の作業を効率化してくれそうです。

"""
        
        for i, article in enumerate(selected_articles, 1):
            # プロダクト名を抽出（タイトルの最初の部分）
            product_name = re.split(r'[–\-]', article['title'])[0].strip()
            
            # 要約を適切な長さに調整
            summary = article['summary']
            if len(summary) > 180:
                summary = summary[:180] + "..."
            elif len(summary) < 60:
                summary = "とても魅力的なプロダクトで、使ってみたくなる機能がたくさんありそうです。"
                
            article_content += f"""## {i}. {product_name}

{summary}

{article['link']}

"""
        
        article_content += f"""## 最後に

今回ご紹介した{len(selected_articles)}つのプロダクト、いかがでしたでしょうか？

気になるものがあれば、ぜひ試してみてくださいね。

公式メディアで、毎日プロダクトリサーチを更新しています！お気軽にチェックしてみてください⬇︎

https://peaky.co.jp/

もし他にも「これは面白い！」というプロダクトをご存知でしたら、コメントで教えていただけると嬉しいです。

---

{' '.join(product_tags)} #プロダクト #最新ツール #便利サービス #テクノロジー #プロダクトハント
"""
        
        return article_content
    
    def save_article(self, content: str) -> str:
        """記事をファイルに保存（クリーンアップ機能付き・JST対応）"""
        # JST時間で日付を取得（GitHub Actions UTC環境対応）
        import pytz
        try:
            jst = pytz.timezone('Asia/Tokyo')
            today = datetime.now(jst).strftime("%Y%m%d")
            timezone_info = "JST"
        except ImportError:
            # pytzが利用できない場合のフォールバック
            # 環境変数TZが設定されている場合はそれを使用
            if os.getenv('TZ') == 'Asia/Tokyo':
                # TZ環境変数が設定されていればdatetime.now()はJSTになる
                today = datetime.now().strftime("%Y%m%d")
                timezone_info = "JST(TZ env)"
            else:
                # フォールバック: UTC+9時間で計算
                today = (datetime.now() + timedelta(hours=9)).strftime("%Y%m%d")
                timezone_info = "JST(UTC+9)"
        
        filename = f"{today}.md"
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            # 記事内容をクリーンアップ
            cleaned_content = self._clean_article_content(content)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(cleaned_content)
            
            print(f"✅ 記事を保存しました: {filepath} ({timezone_info}: {today})")
            return filepath
            
        except Exception as e:
            print(f"❌ ファイル保存エラー: {e}")
            return None

    def _clean_article_content(self, content: str) -> str:
        """記事内容の重複・不要部分をクリーンアップ"""
        lines = content.split('\n')
        cleaned_lines = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # 重複タイトル行を除去
            if line.startswith('タイトル:') and i > 0:
                print(f"🧹 重複タイトル行を除去: {line[:50]}...")
                continue
                
            # 空のMarkdownコードブロック除去
            if line == '```' and i < len(lines) - 1:
                next_line = lines[i + 1].strip()
                if next_line.startswith('キーワード:') or next_line.startswith('blockquote:'):
                    print("🧹 不要なコードブロックを除去")
                    continue
                    
            # Claude APIの出力フォーマット残りを除去
            if any(line.startswith(prefix) for prefix in [
                'キーワード:', 'blockquote:', 'ハッシュタグ:', 
                '```', 'タイトル:', '出力形式', '注意事項'
            ]) and i > 3:  # 記事開始後のフォーマット指示は除去
                print(f"🧹 フォーマット指示を除去: {line[:30]}...")
                continue
                
            cleaned_lines.append(line if line else '')
        
        # 連続する空行を1つにまとめる
        final_lines = []
        prev_empty = False
        
        for line in cleaned_lines:
            if line == '':
                if not prev_empty:
                    final_lines.append(line)
                prev_empty = True
            else:
                final_lines.append(line)
                prev_empty = False
        
        cleaned_content = '\n'.join(final_lines).strip()
        
        # 最終チェック: 記事が正常な構造か確認
        if cleaned_content.startswith('#') and '>' in cleaned_content:
            print("✅ 記事構造の妥当性を確認しました")
        else:
            print("⚠️ 記事構造に問題がある可能性があります")
        
        return cleaned_content
    
    async def run(self):
        """メイン実行処理"""
        print("🚀 Peaky Media プロダクトリサーチ記事まとめ生成開始")
        print("🎯 Product Researchカテゴリのみを対象にします")
        print("=" * 60)
        
        try:
            # 1. RSSフィードからProduct Research記事のみ取得
            articles = self.fetch_peaky_articles()
            
            if not articles:
                print("❌ Product Research記事が取得できませんでした")
                print("💡 Column記事は除外されています")
                return
            
            # 2. 上位記事を選別
            selected_articles = self.select_top_articles(articles, 5)
            
            if len(selected_articles) < 3:
                print("⚠️ 十分なProduct Research記事数が取得できませんでした。")
                print("💡 記事数を確認してください")
                return
            
            # 3. Claude APIで記事生成
            article_content = await self.generate_article_with_claude(selected_articles)
            
            # 4. ファイル保存
            saved_path = self.save_article(article_content)
            
            if saved_path:
                print(f"🎉 プロダクト記事生成完了！")
                print(f"📁 {saved_path}")
                print(f"📊 {len(selected_articles)}つのプロダクトを厳選")
                print(f"✅ Product Researchカテゴリのみを対象に生成")
                
                print(f"\n💡 次のステップ:")
                print(f"   1. 内容確認: cat {saved_path}")
                print(f"   2. Note投稿: python main.py")
            else:
                print("❌ 記事の保存に失敗しました")
                
        except Exception as e:
            print(f"❌ システムエラー: {e}")

async def main():
    """エントリーポイント"""
    try:
        generator = PeakyArticleGenerator()
        await generator.run()
    except ValueError as e:
        print(f"❌ 設定エラー: {e}")
        print("💡 .envファイルにANTHROPIC_API_KEYを設定してください")
    except Exception as e:
        print(f"❌ 予期しないエラー: {e}")

if __name__ == "__main__":
    asyncio.run(main())