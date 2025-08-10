#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Note.com 自動投稿スクリプト
"""

import asyncio
import os
import glob
import shutil
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright
import re
from dotenv import load_dotenv

# 環境変数を読み込み
load_dotenv()

class NoteAutoPoster:
    def __init__(self):
        self.email = os.getenv('NOTE_EMAIL')
        self.password = os.getenv('NOTE_PASSWORD')
        self.base_dir = Path.cwd()
        self.articles_dir = self.base_dir / 'articles'
        
        # ディレクトリ作成
        self.articles_dir.mkdir(exist_ok=True)
        
        if not self.email or not self.password:
            raise ValueError("環境変数 NOTE_EMAIL と NOTE_PASSWORD を設定してください")

    async def run(self):
        """メイン処理：記事を note.com に投稿"""
        print("🚀 Note.com 自動投稿を開始します...")
        
        async with async_playwright() as p:
            # ブラウザ起動
            browser = await p.chromium.launch(
                headless=True,  # ローカルテスト時は False に変更
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            
            try:
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                )
                
                page = await context.new_page()
                
                # Note.comにログイン
                await self.login(page)
                
                # 記事データを取得
                article_data = self.get_article_data()
                
                # 記事を投稿
                await self.create_and_publish_article(page, article_data)
                
                # 投稿済みとしてマーク
                self.mark_as_published(article_data['filename'])
                
                print("✅ 記事の投稿が完了しました！")
                
            except Exception as e:
                print(f"❌ エラーが発生しました: {e}")
                raise
            finally:
                await browser.close()

    async def login(self, page):
        """Note.comにログイン"""
        print("🔐 Note.comにログイン中...")
        
        try:
            await page.goto('https://note.com/login', wait_until='networkidle')
            
            # メールアドレス入力
            print("📧 メールアドレスを入力中...")
            email_input = await page.wait_for_selector('#email', timeout=10000)
            await email_input.fill(self.email)
            
            # パスワード入力
            print("🔒 パスワードを入力中...")
            password_input = await page.wait_for_selector('#password', timeout=10000)
            await password_input.fill(self.password)
            
            # 少し待機してボタンが有効になるのを待つ
            await page.wait_for_timeout(1000)
            
            # ログインボタンをクリック
            print("🔘 ログインボタンをクリック中...")
            login_button_selectors = [
                'button:has-text("ログイン")',
                'button[data-type="primaryNext"]',
                'button:has-text("ログイン"):not([disabled])',
                '.a-button:has-text("ログイン")'
            ]
            
            login_clicked = False
            for selector in login_button_selectors:
                try:
                    button = page.locator(selector).first
                    if await button.is_visible():
                        # disabledでないことを確認
                        if not await button.is_disabled():
                            await button.click()
                            login_clicked = True
                            print("✅ ログインボタンクリック完了")
                            break
                        else:
                            print(f"⚠️ ボタンが無効状態: {selector}")
                except Exception as e:
                    print(f"⚠️ ボタンクリック試行失敗: {selector} - {e}")
                    continue
            
            if not login_clicked:
                raise Exception("ログインボタンが見つからないか、クリックできません")
            
            # ナビゲーション待機
            try:
                await page.wait_for_navigation(wait_until='networkidle', timeout=10000)
            except:
                # ナビゲーションが発生しない場合もあるので、URL変化をチェック
                await page.wait_for_timeout(3000)
            
            # ログイン成功確認
            current_url = page.url
            print(f"🌐 現在のURL: {current_url}")
            
            if "login" in current_url:
                # エラーメッセージを確認
                error_messages = await page.locator('.o-login__error, .o-login__cakes-error').all()
                if error_messages:
                    error_text = await error_messages[0].text_content()
                    raise Exception(f"ログインに失敗しました: {error_text}")
                else:
                    raise Exception("ログインに失敗しました。認証情報を確認してください。")
            
            print("✅ ログイン完了")
            
        except Exception as e:
            print(f"❌ ログインエラー: {e}")
            raise

    def get_article_data(self):
        """記事データを取得"""
        print("📄 記事データを取得中...")
        
        # Markdownファイルを検索
        md_files = list(self.articles_dir.glob('*.md'))
        
        if not md_files:
            # 記事がない場合は自動生成
            return self.generate_auto_article()
        
        # 最初のファイルを取得（日付順にソート）
        md_files.sort()
        article_file = md_files[0]
        
        try:
            with open(article_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # タイトル抽出（# で始まる行）
            title = article_file.stem  # ファイル名をデフォルトタイトルに
            title_match = re.search(r'^#\s+(.+)', content, re.MULTILINE)
            if title_match:
                title = title_match.group(1).strip()
            
            print(f"📰 記事タイトル: {title}")
            
            return {
                'title': title,
                'content': content,
                'filename': article_file.name
            }
            
        except Exception as e:
            print(f"⚠️ 記事ファイル読み込みエラー: {e}")
            return self.generate_auto_article()

    def generate_auto_article(self):
        """自動記事生成"""
        print("🤖 記事を自動生成中...")
        
        today = datetime.now()
        date_str = today.strftime('%Y年%m月%d日')
        
        title = f"{date_str} - 今日の学び"
        
        content = f"""# {title}

こんにちは！今日は{date_str}です。

## 今日のポイント

今日は自動投稿システムを使って記事を投稿しています。

### 技術的な学び

- Python + Playwright での自動化
- GitHub Actions による継続的投稿
- Markdownでの記事管理

### 今後の目標

- より充実したコンテンツ作成
- 読者の方との交流促進
- 継続的な学習と発信

## まとめ

継続的な発信を心がけて、日々の学びを共有していきたいと思います。
技術的な挑戦も楽しみながら進めていきます！

---
*この記事は自動投稿システムによって投稿されました。*

#プログラミング #自動化 #学習記録 #継続"""

        return {
            'title': title,
            'content': content,
            'filename': f'auto-{today.strftime("%Y%m%d")}.md'
        }

    async def create_and_publish_article(self, page, article_data):
        """記事を作成して投稿"""
        print("📝 記事投稿ページに移動中...")
        
        try:
            await page.goto('https://note.com/new', wait_until='networkidle')
            
            # タイトル入力
            print(f"📰 タイトルを入力: {article_data['title']}")
            await self.input_title(page, article_data['title'])
            
            # 本文入力
            print("📄 本文を入力中...")
            await self.input_content(page, article_data['content'])
            
            # 少し待機
            await page.wait_for_timeout(2000)
            
            # 公開処理
            await self.publish_article(page)
            
        except Exception as e:
            print(f"❌ 記事作成エラー: {e}")
            raise

    async def input_title(self, page, title):
        """タイトル入力"""
        title_selectors = [
            'input[placeholder*="タイトル"]',
            'input[data-testid="title-input"]',
            '.note-editor-title input',
            'input[name="title"]',
            '.editor-title input'
        ]
        
        for selector in title_selectors:
            try:
                element = await page.wait_for_selector(selector, timeout=5000)
                await element.fill(title)
                return
            except:
                continue
        
        raise Exception("タイトル入力欄が見つかりません")

    async def input_content(self, page, content):
        """本文入力"""
        content_selectors = [
            '[contenteditable="true"]',
            '.note-editor-content',
            '.editor-content',
            '[data-testid="editor-content"]',
            '.editor-body [contenteditable]'
        ]
        
        for selector in content_selectors:
            try:
                element = await page.wait_for_selector(selector, timeout=5000)
                await element.click()
                await page.keyboard.type(content)
                return
            except:
                continue
        
        raise Exception("本文入力欄が見つかりません")

    async def publish_article(self, page):
        """記事を公開"""
        print("🚀 記事を公開中...")
        
        publish_selectors = [
            'button:has-text("公開する")',
            'button:has-text("投稿する")',
            'button[data-testid="publish-button"]',
            'button:has-text("公開")',
            '.publish-button'
        ]
        
        for selector in publish_selectors:
            try:
                button = page.locator(selector).first
                if await button.is_visible():
                    await button.click()
                    print("📤 公開ボタンをクリックしました")
                    
                    # 公開確認ダイアログがある場合
                    await page.wait_for_timeout(1000)
                    confirm_selectors = [
                        'button:has-text("公開する")',
                        'button:has-text("確認")',
                        'button:has-text("投稿")'
                    ]
                    
                    for confirm_selector in confirm_selectors:
                        try:
                            confirm_button = page.locator(confirm_selector).first
                            if await confirm_button.is_visible():
                                await confirm_button.click()
                                break
                        except:
                            continue
                    
                    await page.wait_for_timeout(3000)
                    return
            except:
                continue
        
        # 公開ボタンが見つからない場合は下書き保存
        print("⚠️ 公開ボタンが見つからないため、下書き保存を試行します")
        save_selectors = [
            'button:has-text("下書き保存")',
            'button:has-text("保存")',
            '.save-button'
        ]
        
        for selector in save_selectors:
            try:
                button = page.locator(selector).first
                if await button.is_visible():
                    await button.click()
                    print("💾 下書きとして保存しました")
                    return
            except:
                continue
        
        print("⚠️ 投稿処理を完了できませんでした")

    def mark_as_published(self, filename):
        """投稿済みファイルを処理"""
        if filename.startswith('auto-'):
            print("🤖 自動生成記事のため、ファイル処理はスキップします")
            return
        
        try:
            source_path = self.articles_dir / filename
            if source_path.exists():
                # 投稿済みファイル名に変更
                published_name = f"published_{datetime.now().strftime('%Y%m%d')}_{filename}"
                target_path = self.articles_dir / published_name
                
                source_path.rename(target_path)
                print(f"📁 記事ファイルをリネーム: {filename} → {published_name}")
        except Exception as e:
            print(f"⚠️ ファイル処理エラー: {e}")


async def main():
    """メイン関数"""
    try:
        poster = NoteAutoPoster()
        await poster.run()
    except Exception as e:
        print(f"💥 実行エラー: {e}")
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())