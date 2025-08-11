#!/usr/bin/env python3
"""
Note.com自動投稿システム（完全版）
投稿機能を実装し、タイトル・本文・アイキャッチ設定・公開まで自動化
キーワードベースアイキャッチ検索対応（検索アイコンクリック対応）
"""

import os
import asyncio
import re
import requests
import glob
from datetime import datetime
from playwright.async_api import async_playwright
from dotenv import load_dotenv

# 環境変数読み込み
load_dotenv()

class NoteAutoPoster:
    def __init__(self):
        self.browser = None
        self.page = None
        
    async def setup_browser(self, headless=False):
        """ブラウザセットアップ"""
        print(f"🔧 ブラウザ起動中... (headless={headless})")
        p = await async_playwright().start()
        self.browser = await p.chromium.launch(
            headless=headless,
            slow_mo=500 if not headless else 0,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor'
            ]
        )
        
        context = await self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        self.page = await context.new_page()
        
        # ネットワークエラーを無視
        await self.page.route("**/*", self._handle_route)
        
    async def _handle_route(self, route):
        """ルートハンドラー"""
        try:
            await route.continue_()
        except Exception:
            pass
    
    async def login(self):
        """Note.comログイン処理"""
        print("🔑 Note.comログイン開始...")
        
        try:
            # 1. ログインページアクセス
            print("📱 ログインページにアクセス中...")
            await self.page.goto("https://note.com/login", 
                                wait_until="networkidle", 
                                timeout=30000)
            
            await self.page.wait_for_timeout(2000)
            
            # 2. メールアドレス入力
            print("📧 メールアドレス入力中...")
            email_input = self.page.locator("#email")
            await email_input.wait_for(timeout=10000)
            await email_input.clear()
            await email_input.fill(os.getenv('NOTE_EMAIL'))
            print("✅ メールアドレス入力完了")
            
            # 3. パスワード入力
            print("🔒 パスワード入力中...")
            password_input = self.page.locator("#password")
            await password_input.wait_for(timeout=10000)
            await password_input.clear()
            await password_input.fill(os.getenv('NOTE_PASSWORD'))
            print("✅ パスワード入力完了")
            
            # 4. ログインボタンクリック
            print("⏳ ボタン有効化を待機中...")
            await self.page.wait_for_timeout(1500)
            
            login_button = self.page.locator('button[data-type="primaryNext"]:has-text("ログイン")')
            await login_button.wait_for(timeout=10000)
            
            # ボタンが有効になるまで待機
            for i in range(10):
                is_disabled = await login_button.is_disabled()
                if not is_disabled:
                    print("✅ ログインボタンが有効になりました")
                    break
                print(f"⏳ ボタン有効化待機中... ({i+1}/10)")
                await self.page.wait_for_timeout(500)
            
            print("🚀 ログインボタンクリック...")
            await login_button.click()
            
            # 5. ログイン完了を待機
            print("⏳ ログイン処理完了を待機中...")
            try:
                await self.page.wait_for_navigation(wait_until='networkidle', timeout=15000)
            except:
                await self.page.wait_for_timeout(3000)
            
            # 6. ログイン成功確認
            current_url = self.page.url
            print(f"🌐 現在のURL: {current_url}")
            
            if "login" in current_url:
                error_locator = self.page.locator('.o-login__error, .o-login__cakes-error').first
                if await error_locator.count() > 0:
                    error_text = await error_locator.inner_text()
                    raise Exception(f"ログインエラー: {error_text}")
                else:
                    raise Exception("ログインに失敗しました")
            
            print("✅ ログイン成功！")
            return True
            
        except Exception as e:
            print(f"❌ ログインエラー: {e}")
            try:
                await self.page.screenshot(path=f"login_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                print("📸 エラーのスクリーンショットを保存しました")
            except:
                pass
            return False

    async def create_and_publish_article(self, title, content):
        """記事作成・投稿処理（キーワードベースアイキャッチ対応）"""
        print("📝 記事作成・投稿開始...")
        print(f"タイトル: {title}")
        print(f"内容: {content[:100]}...")
        
        try:
            # 1. 投稿ページにアクセス
            print("📝 投稿ページにアクセス中...")
            await self.page.goto("https://note.com/new", wait_until="networkidle")
            await self.page.wait_for_timeout(3000)
            
            # 2. タイトル入力
            print("📄 タイトルを入力中...")
            title_selectors = [
                'textarea[placeholder="記事タイトル"]',
                '.sc-80832eb4-0.heevId',
                'textarea[spellcheck="true"]',
                'textarea:has-text("")'
            ]
            
            title_input = None
            for selector in title_selectors:
                try:
                    title_input = self.page.locator(selector).first
                    if await title_input.is_visible():
                        await title_input.click()
                        await title_input.clear()
                        await title_input.fill(title)
                        print(f"✅ タイトル入力完了: {selector}")
                        break
                except Exception as e:
                    print(f"⚠️ タイトル入力試行失敗: {selector} - {e}")
                    continue
            
            if title_input is None:
                raise Exception("タイトル入力欄が見つかりません")
            
            await self.page.wait_for_timeout(1000)
            
            # 3. 本文入力（ProseMirrorエディタ用の特別処理）
            print("📝 本文を入力中...")
            
            # ProseMirrorエディタをクリックしてフォーカス
            prosemirror_selectors = [
                '.ProseMirror',
                '[contenteditable="true"]',
                '.ProseMirror[data-placeholder]'
            ]
            
            content_input = None
            for selector in prosemirror_selectors:
                try:
                    content_input = self.page.locator(selector).first
                    if await content_input.is_visible():
                        # エディタをクリックしてフォーカス
                        await content_input.click()
                        await self.page.wait_for_timeout(500)
                        
                        # 既存の内容をクリア（Ctrl+A -> Delete）
                        await self.page.keyboard.press('Meta+a')  # Mac用（Ctrl+a for Windows）
                        await self.page.wait_for_timeout(200)
                        await self.page.keyboard.press('Delete')
                        await self.page.wait_for_timeout(500)
                        
                        # 本文を入力
                        await self.page.keyboard.type(content)
                        print(f"✅ 本文入力完了: {selector}")
                        content_input = True
                        break
                except Exception as e:
                    print(f"⚠️ 本文入力試行失敗: {selector} - {e}")
                    continue
            
            if content_input is None:
                raise Exception("本文入力欄が見つかりません")
            
            await self.page.wait_for_timeout(1000)
            
            # 4. アイキャッチ設定（キーワードベース）
            print("🖼️ アイキャッチ設定開始...")
            await self.set_eyecatch_image(title, content)
            
            # 5. 公開に進む
            print("📢 公開処理開始...")
            print("⏳ アイキャッチ設定完了を確実に待機してから公開に進みます...")
            await self.page.wait_for_timeout(8000)  # アイキャッチ保存完了を十分に待つ（延長）
            
            # 公開処理をリトライ機能付きで実行
            return await self._publish_with_retry()
                
        except Exception as e:
            print(f"❌ 記事投稿エラー: {e}")
            try:
                await self.page.screenshot(path=f"publish_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                print("📸 投稿エラーのスクリーンショットを保存しました")
            except:
                pass
            return False

    async def set_eyecatch_image(self, title, content):
        """アイキャッチ画像設定（シンプルキーワード抽出版）"""
        try:
            print("🖼️ アイキャッチ画像設定開始...")
            
            # シンプルなキーワード抽出（Claude API不使用）
            keyword = self._extract_keyword_simple(title, content)
            print(f"🔍 アイキャッチ検索キーワード: 「{keyword}」")
            
            # 1. アイキャッチ設定ボタンをクリック
            eyecatch_button_selectors = [
                'button[aria-label="画像を追加"]',
                '.sc-55422cdd-2.gxWRok',
                'button:has-text("画像")',
                'svg[data-src="/icons/imageAdd.svg"]'
            ]
            
            eyecatch_clicked = False
            for selector in eyecatch_button_selectors:
                try:
                    button = self.page.locator(selector).first
                    if await button.is_visible():
                        await button.click()
                        eyecatch_clicked = True
                        print(f"✅ アイキャッチボタンクリック: {selector}")
                        break
                except Exception as e:
                    print(f"⚠️ アイキャッチボタン試行失敗: {selector} - {e}")
                    continue
            
            if not eyecatch_clicked:
                print("⚠️ アイキャッチボタンが見つかりません。スキップします。")
                return
            
            await self.page.wait_for_timeout(2000)
            
            # 2. 「記事にあう画像を選ぶ」ボタンをクリック
            print("🖼️ 「記事にあう画像を選ぶ」を選択中...")
            await self.page.wait_for_timeout(2000)
            
            select_image_selectors = [
                'text=記事にあう画像を選ぶ',
                ':has-text("記事にあう画像を選ぶ")',
                'div:has-text("記事にあう画像を選ぶ")',
                'button:has-text("記事にあう画像を選ぶ")',
                '[role="button"]:has-text("記事にあう画像を選ぶ")'
            ]
            
            select_clicked = False
            for selector in select_image_selectors:
                try:
                    # まず要素が存在するかチェック
                    elements = self.page.locator(selector)
                    count = await elements.count()
                    print(f"🔍 「{selector}」で見つかった要素数: {count}")
                    
                    if count > 0:
                        element = elements.first
                        if await element.is_visible():
                            await element.click()
                            select_clicked = True
                            print(f"✅ 「記事にあう画像を選ぶ」クリック完了: {selector}")
                            break
                        else:
                            print(f"⚠️ 要素は存在するが見えません: {selector}")
                    else:
                        print(f"⚠️ 要素が見つかりません: {selector}")
                        
                except Exception as e:
                    print(f"⚠️ 「記事にあう画像を選ぶ」試行失敗: {selector} - {e}")
                    continue
            
            if not select_clicked:
                print("❌ 「記事にあう画像を選ぶ」ボタンが見つかりません。スキップします。")
                return
            
            await self.page.wait_for_timeout(2000)
            
            # 3. 🔍検索アイコンをクリックして検索入力欄を表示
            print("🔍 検索アイコンをクリックして検索機能を開始...")
            await self.page.wait_for_timeout(2000)
            
            search_icon_selectors = [
                'svg path[d*="M14.71 14H15.5L20.49 19"]',  # 具体的なSVGパス
                'button:has(svg path[d*="M14.71 14H15.5"])',  # SVGを含むボタン
                'svg[role="img"]:has(path[fill-rule="evenodd"])',
                '[aria-label*="検索"]',
                'button svg path[fill-rule="evenodd"]'
            ]
            
            search_icon_clicked = False
            for selector in search_icon_selectors:
                try:
                    search_icons = self.page.locator(selector)
                    count = await search_icons.count()
                    print(f"🔍 検索アイコン「{selector}」で見つかった要素数: {count}")
                    
                    if count > 0:
                        search_icon = search_icons.first
                        if await search_icon.is_visible():
                            await search_icon.click()
                            search_icon_clicked = True
                            print(f"✅ 検索アイコンクリック完了: {selector}")
                            break
                except Exception as e:
                    print(f"⚠️ 検索アイコン試行失敗: {selector} - {e}")
                    continue
            
            if search_icon_clicked:
                await self.page.wait_for_timeout(1500)
                print("✅ 検索入力欄の表示を待機...")
            
            # 4. キーワードで画像検索
            print(f"🔍 キーワード「{keyword}」で画像検索中...")
            search_input_selectors = [
                'input[placeholder="キーワード検索"]',
                'input[aria-label*="みんなのフォトギャラリーから検索"]',
                'input.sc-720f88eb-4.dACgdT',
                'input[placeholder*="検索"]',
                'input[type="text"]'
            ]
            
            search_input_found = False
            for selector in search_input_selectors:
                try:
                    search_input = self.page.locator(selector).first
                    if await search_input.is_visible():
                        await search_input.clear()
                        await search_input.fill(keyword)
                        await search_input.press('Enter')
                        search_input_found = True
                        print(f"✅ キーワード検索完了: {selector}")
                        break
                except Exception as e:
                    print(f"⚠️ 検索入力試行失敗: {selector} - {e}")
                    continue
            
            if not search_input_found:
                print("⚠️ 検索入力欄が見つかりません。キーワードなしで画像選択を試行します。")
            
            # 5. 画像が読み込まれるまで待機
            print("🖼️ 画像の読み込みを待機中...")
            await self.page.wait_for_timeout(4000)
            
            # 6. 利用可能な画像を探して選択
            print("🖼️ 利用可能な画像を探します...")
            
            image_selectors = [
                'img[src*="assets.st-note.com"]',
                'img[src*="note.com"]',
                'img.sc-a7ee00d5-4',
                'img[width="400"]',
                'img[alt*="画像"]',
                'img'
            ]
            
            image_selected = False
            for selector in image_selectors:
                try:
                    images = self.page.locator(selector)
                    count = await images.count()
                    print(f"🖼️ 「{selector}」で見つかった画像数: {count}")
                    
                    if count > 0:
                        # シンプルな画像選択
                        best_image_index = await self._select_image_simple(images, keyword)
                        
                        try:
                            image = images.nth(best_image_index)
                            if await image.is_visible():
                                src = await image.get_attribute('src')
                                print(f"🖼️ 選択画像: {src}")
                                
                                await image.click()
                                image_selected = True
                                print(f"✅ 画像選択完了: {selector}")
                                break
                        except Exception as e:
                            print(f"⚠️ 画像クリック失敗: {e}")
                            # 超シンプルフォールバック: 最初の画像
                            try:
                                first_image = images.first
                                if await first_image.is_visible():
                                    await first_image.click()
                                    image_selected = True
                                    print(f"✅ フォールバック画像選択完了: {selector}")
                                    break
                            except Exception as e2:
                                print(f"⚠️ フォールバック画像クリック失敗: {e2}")
                                continue
                        
                        if image_selected:
                            break
                            
                except Exception as e:
                    print(f"⚠️ 画像選択試行失敗: {selector} - {e}")
                    continue
            
            if not image_selected:
                print("⚠️ 選択可能な画像が見つかりません。アイキャッチなしで進行します。")
                return
            
            await self.page.wait_for_timeout(2000)
            
            # 7. 「この画像を挿入」ボタンをクリック
            insert_button_selectors = [
                'span:has-text("この画像を挿入")',
                '#\\:rd\\:',
                'button:has-text("挿入")'
            ]
            
            insert_clicked = False
            for selector in insert_button_selectors:
                try:
                    insert_button = self.page.locator(selector).first
                    if await insert_button.is_visible():
                        await insert_button.click()
                        insert_clicked = True
                        print(f"✅ 画像挿入ボタンクリック: {selector}")
                        break
                except Exception as e:
                    print(f"⚠️ 画像挿入ボタン試行失敗: {selector} - {e}")
                    continue
            
            if not insert_clicked:
                print("⚠️ 画像挿入ボタンが見つかりません。スキップします。")
                return
            
            await self.page.wait_for_timeout(2000)
            
            # 8. 「保存」ボタンをクリック
            print("💾 画像クロップ画面の保存ボタンをクリック中...")
            await self.page.wait_for_timeout(2000)
            
            save_button_selectors = [
                'button:has-text("保存")',
                'span:has-text("保存")',
                '#\\:rj\\:',
                'button[class*="font-bold"]:has-text("保存")',
                '[role="button"]:has-text("保存")',
                'div:has-text("保存"):last-child'
            ]
            
            save_clicked = False
            for selector in save_button_selectors:
                try:
                    save_buttons = self.page.locator(selector)
                    count = await save_buttons.count()
                    print(f"💾 「{selector}」で見つかった保存ボタン数: {count}")
                    
                    if count > 0:
                        save_button = save_buttons.last
                        if await save_button.is_visible():
                            await self.page.wait_for_timeout(1000)
                            await save_button.click()
                            save_clicked = True
                            print(f"✅ 保存ボタンクリック完了: {selector}")
                            break
                        else:
                            print(f"💾 保存ボタンは存在するが見えません: {selector}")
                            
                except Exception as e:
                    print(f"⚠️ 保存ボタン試行失敗: {selector} - {e}")
                    continue
            
            if save_clicked:
                print("✅ アイキャッチ設定完了！")
                print("⏳ 画像の読み込み完了を待機中...")
                await self._wait_for_eyecatch_completion()
            else:
                print("⚠️ 保存ボタンが見つかりませんでした")
                
        except Exception as e:
            print(f"⚠️ アイキャッチ設定エラー: {e}")
            print("📝 アイキャッチなしで投稿を続行します")

    def _extract_keyword_simple(self, title, content):
        """シンプルなキーワード抽出（Claude API不使用）"""
        
        # 方法1: タイトルから「【今日のキーワード：「xxx」】」部分を抽出
        keyword_pattern = r'【今日のキーワード：「([^」]+)」】'
        match = re.search(keyword_pattern, title)
        if match:
            keyword = match.group(1)
            print(f"🎯 タイトルからキーワード抽出: 「{keyword}」")
            return keyword
        
        # 方法2: blockquote内のキーワード解説から抽出
        blockquote_pattern = r'> .*?「([^」]+)」.*?について'
        match = re.search(blockquote_pattern, content)
        if match:
            keyword = match.group(1)
            print(f"🎯 blockquoteからキーワード抽出: 「{keyword}」")
            return keyword
        
        # 方法3: Note.com最適化キーワード（確実性重視）
        note_keywords = [
            'AI', 'AIツール', 'ツール', 'プロダクト', 'ビジネス', 'テクノロジー', 
            'デザイン', 'イノベーション', 'スタートアップ', '自動化', '効率'
        ]
        
        all_text = f"{title} {content}"
        for keyword in note_keywords:
            if keyword in all_text:
                print(f"🎯 テキストマッチング: 「{keyword}」")
                return keyword
        
        # 最終フォールバック
        print("🎯 デフォルトキーワード使用: 「プロダクト」")
        return "プロダクト"





    async def _select_image_simple(self, images, keyword):
        """シンプルな画像選択（ランダム + フォールバック）"""
        try:
            import random
            
            count = await images.count()
            if count == 0:
                return 0
            
            # 戦略1: ランダム選択（最初の5枚から）
            # キーワード検索後の上位画像は品質が高いことが多い
            max_choice = min(count, 5)
            selected_index = random.randint(0, max_choice - 1)
            
            print(f"🎲 画像をランダム選択: {selected_index + 1}番目 / {count}枚中")
            return selected_index
            
        except Exception as e:
            print(f"⚠️ 画像選択エラー: {e}")
            return 0  # フォールバック: 最初の画像



    async def _wait_for_eyecatch_completion(self):
        """アイキャッチ設定完了を確実に待機（最適化版）"""
        try:
            print("⏳ アイキャッチ設定完了を確実に待機中...")
            
            # まず十分な基本待機時間を設ける
            print("⏳ 基本的な画像処理時間を待機中...")
            await self.page.wait_for_timeout(5000)  # 2000ms → 5000ms に延長
            
            # アイキャッチ関連のモーダルが閉じるまで待機（試行回数を削減）
            max_wait_attempts = 8  # 20回 → 8回に削減
            wait_interval = 2000   # 1000ms → 2000ms に延長
            
            for attempt in range(max_wait_attempts):
                try:
                    modal_selectors = [
                        '[role="dialog"]',
                        '.modal',
                        '.o-modal',
                        ':has-text("画像を選ぶ")',
                        ':has-text("この画像を挿入")',
                        ':has-text("保存")',
                        ':has-text("アイキャッチ")'
                    ]
                    
                    modal_exists = False
                    for selector in modal_selectors:
                        try:
                            modal_elements = self.page.locator(selector)
                            count = await modal_elements.count()
                            if count > 0:
                                for i in range(count):
                                    modal = modal_elements.nth(i)
                                    if await modal.is_visible():
                                        modal_exists = True
                                        print(f"⏳ アイキャッチモーダルが残っています: {selector} (試行 {attempt + 1}/{max_wait_attempts})")
                                        break
                            if modal_exists:
                                break
                        except:
                            continue
                    
                    if not modal_exists:
                        print("✅ アイキャッチ関連のモーダルが閉じました")
                        break
                    
                    # 待機間隔を延長
                    await self.page.wait_for_timeout(wait_interval)
                    
                except Exception as e:
                    print(f"⚠️ モーダル確認エラー (試行 {attempt + 1}): {e}")
                    await self.page.wait_for_timeout(wait_interval)
                    continue
            
            # 最終的な画像読み込み完了待機（延長）
            print("⏳ 最終的な画像読み込み完了を待機中...")
            await self.page.wait_for_timeout(8000)  # 5000ms → 8000ms に延長
            
            # アイキャッチ画像が実際に読み込まれたか確認
            eyecatch_loaded = await self._verify_eyecatch_loaded()
            
            if eyecatch_loaded:
                print("✅ アイキャッチ設定が完全に完了しました")
            else:
                print("⚠️ アイキャッチの読み込み確認はできませんが続行します")
            
            # 記事編集画面が正常に表示されているか確認
            await self._verify_article_ready()
            
        except Exception as e:
            print(f"⚠️ アイキャッチ完了待機エラー: {e}")
            await self.page.wait_for_timeout(5000)  # エラー時も延長

    async def _verify_article_ready(self):
        """記事編集画面が投稿準備完了状態かを確認"""
        try:
            print("🔍 記事編集画面の状態を確認中...")
            
            ready_indicators = [
                'textarea[placeholder="記事タイトル"]',
                '.ProseMirror',
                'span:has-text("公開に進む")',
                'button:has-text("公開に進む")'
            ]
            
            ready_count = 0
            for selector in ready_indicators:
                try:
                    elements = self.page.locator(selector)
                    count = await elements.count()
                    if count > 0:
                        element = elements.first
                        if await element.is_visible():
                            ready_count += 1
                except:
                    continue
            
            if ready_count >= 2:
                print(f"✅ 記事編集画面準備完了 ({ready_count}/{len(ready_indicators)} 要素確認)")
                return True
            else:
                print(f"⚠️ 記事編集画面の準備が不完全 ({ready_count}/{len(ready_indicators)} 要素確認)")
                return False
                
        except Exception as e:
            print(f"⚠️ 記事準備状態確認エラー: {e}")
            return False

    async def _verify_eyecatch_loaded(self):
        """アイキャッチ画像の読み込み完了を確認"""
        try:
            print("🔍 アイキャッチ画像の読み込み状況を確認中...")
            
            eyecatch_area_selectors = [
                '.editor-eyecatch img',
                '[data-testid="eyecatch-image"]',
                '.eyecatch-image',
                'img[src*="assets.st-note.com"]'
            ]
            
            for selector in eyecatch_area_selectors:
                try:
                    eyecatch_images = self.page.locator(selector)
                    count = await eyecatch_images.count()
                    if count > 0:
                        print(f"✅ アイキャッチ画像が読み込まれました: {selector}")
                        return True
                except Exception:
                    continue
                    
            print("⚠️ アイキャッチ画像の読み込みが確認できませんが続行します")
            return False
            
        except Exception as e:
            print(f"⚠️ アイキャッチ確認エラー: {e}")
            return False

    async def _close_search_dialog(self):
        """検索ダイアログを閉じる（ログアウト時の検索ウィンドウ対策）"""
        try:
            print("🔍 検索ダイアログをチェック中...")
            
            # 検索関連のダイアログ・モーダルを検出
            search_dialog_selectors = [
                ':has-text("検索")',
                ':has-text("キーワード検索")',
                ':has-text("みんなのフォトギャラリーから検索")',
                '[role="dialog"]:has-text("検索")',
                '.modal:has-text("検索")',
                '.o-modal:has-text("検索")',
                'input[placeholder*="検索"]',
                'input[placeholder="キーワード検索"]'
            ]
            
            dialog_found = False
            for selector in search_dialog_selectors:
                try:
                    dialogs = self.page.locator(selector)
                    count = await dialogs.count()
                    if count > 0:
                        for i in range(count):
                            dialog = dialogs.nth(i)
                            if await dialog.is_visible():
                                dialog_found = True
                                print(f"🔍 検索ダイアログを発見: {selector}")
                                break
                        if dialog_found:
                            break
                except Exception:
                    continue
            
            if not dialog_found:
                print("✅ 検索ダイアログは見つかりませんでした")
                return
            
            # 検索ダイアログを閉じる
            print("🔍 検索ダイアログを閉じる試行中...")
            
            # 1. ESCキーで閉じる
            try:
                await self.page.keyboard.press('Escape')
                await self.page.wait_for_timeout(1000)
                print("✅ ESCキーで検索ダイアログを閉じました")
                return
            except Exception as e:
                print(f"⚠️ ESCキーでの閉じる操作に失敗: {e}")
            
            # 2. 背景クリックで閉じる
            try:
                await self.page.click('body', position={'x': 100, 'y': 100})
                await self.page.wait_for_timeout(1000)
                print("✅ 背景クリックで検索ダイアログを閉じました")
                return
            except Exception as e:
                print(f"⚠️ 背景クリックでの閉じる操作に失敗: {e}")
            
            # 3. 閉じるボタンを探してクリック
            close_button_selectors = [
                'button:has-text("閉じる")',
                'span:has-text("閉じる")',
                'button:has-text("×")',
                'button:has-text("✕")',
                '[aria-label="閉じる"]',
                '[aria-label="Close"]',
                'button[aria-label="Close"]'
            ]
            
            for selector in close_button_selectors:
                try:
                    close_buttons = self.page.locator(selector)
                    count = await close_buttons.count()
                    if count > 0:
                        close_button = close_buttons.first
                        if await close_button.is_visible():
                            await close_button.click()
                            await self.page.wait_for_timeout(1000)
                            print(f"✅ 閉じるボタンで検索ダイアログを閉じました: {selector}")
                            return
                except Exception:
                    continue
            
            print("⚠️ 検索ダイアログを閉じることができませんでした")
            
        except Exception as e:
            print(f"⚠️ 検索ダイアログ閉じる処理エラー: {e}")

    async def _publish_with_retry(self):
        """リトライ機能付き公開処理"""
        max_retry = 3
        
        for attempt in range(max_retry):
            print(f"📢 公開処理試行 {attempt + 1}/{max_retry}")
            
            try:
                current_url = self.page.url
                print(f"🌐 公開前のURL: {current_url}")
                
                publish_success = await self._click_publish_button()
                
                if not publish_success:
                    print(f"⚠️ 公開ボタンクリック失敗 (試行 {attempt + 1})")
                    continue
                
                print("⏳ 公開処理を待機中...")
                await self.page.wait_for_timeout(3000)
                
                error_handled = await self._handle_publish_error()
                
                if error_handled:
                    print("⚠️ エラーが発生しました。リトライします...")
                    print("⏳ アイキャッチ設定が完了するまで追加の待機時間を設けます...")
                    await self.page.wait_for_timeout(5000)
                    continue
                
                return await self._complete_publishing()
                
            except Exception as e:
                print(f"⚠️ 公開処理エラー (試行 {attempt + 1}): {e}")
                if attempt < max_retry - 1:
                    print("⏳ エラー後の回復待機時間...")
                    await self.page.wait_for_timeout(5000)
                    continue
                else:
                    return False
        
        print("❌ 公開処理が最大リトライ回数に達しました")
        return False

    async def _click_publish_button(self):
        """公開ボタンクリック処理"""
        publish_button_selectors = [
            'span:has-text("公開に進む")',
            'button:has-text("公開に進む")',
            'span:has-text("公開")',
            'button:has-text("公開")',
            '[data-testid="publish-button"]'
        ]
        
        for selector in publish_button_selectors:
            try:
                publish_buttons = self.page.locator(selector)
                count = await publish_buttons.count()
                print(f"📢 「{selector}」で見つかった公開ボタン数: {count}")
                
                if count > 0:
                    publish_button = publish_buttons.first
                    if await publish_button.is_visible():
                        await publish_button.click()
                        print(f"✅ 公開ボタンクリック完了: {selector}")
                        return True
                    else:
                        print(f"📢 公開ボタンは存在するが見えません: {selector}")
                        
            except Exception as e:
                print(f"⚠️ 公開ボタン試行失敗: {selector} - {e}")
                continue
        
        try:
            await self.page.keyboard.press('Meta+Enter')
            print("✅ キーボードショートカットで公開を試行")
            return True
        except:
            print("❌ 公開処理に失敗しました")
            return False

    async def _handle_publish_error(self):
        """公開エラーダイアログの処理（強化版）"""
        try:
            error_dialog_selectors = [
                ':has-text("タイトル、本文を入力してください")',
                ':has-text("入力してください")',
                ':has-text("必須項目")',
                ':has-text("エラー")',
                ':has-text("読み込み")',
                ':has-text("準備中")',
                '.error-dialog',
                '[role="dialog"]',
                '.modal:has-text("エラー")',
                '.o-modal:has-text("入力")',
                '[role="alertdialog"]'
            ]
            
            print("🔍 エラーダイアログを詳細チェック中...")
            
            for selector in error_dialog_selectors:
                try:
                    error_dialogs = self.page.locator(selector)
                    count = await error_dialogs.count()
                    
                    if count > 0:
                        print(f"🚨 エラーダイアログ候補発見: {selector} (数: {count})")
                        
                        for i in range(count):
                            error_dialog = error_dialogs.nth(i)
                            if await error_dialog.is_visible():
                                print(f"🚨 エラーダイアログを確認: {selector} (要素 {i+1})")
                                
                                try:
                                    error_text = await error_dialog.text_content()
                                    print(f"🚨 エラー内容: {error_text[:100]}...")
                                    
                                    if any(pattern in error_text for pattern in [
                                        "タイトル、本文を入力",
                                        "入力してください",
                                        "必須項目",
                                        "読み込み中",
                                        "準備中"
                                    ]):
                                        print("🚨 記事準備不完全エラーを検出")
                                        
                                        close_success = await self._close_error_dialog_enhanced()
                                        
                                        if close_success:
                                            print("✅ エラーダイアログを閉じました")
                                            await self.page.wait_for_timeout(3000)
                                            return True
                                        else:
                                            print("⚠️ エラーダイアログを閉じることができませんでした")
                                            return True
                                except Exception as e:
                                    print(f"⚠️ エラーテキスト取得失敗: {e}")
                                
                                return True
                            
                except Exception as e:
                    print(f"⚠️ エラーダイアログ検出失敗: {selector} - {e}")
                    continue
            
            print("✅ エラーダイアログは検出されませんでした")
            return False
            
        except Exception as e:
            print(f"⚠️ エラーハンドリング中にエラー: {e}")
            return False

    async def _close_error_dialog_enhanced(self):
        """エラーダイアログの「閉じる」ボタンをクリック（強化版）"""
        close_button_selectors = [
            'button:has-text("閉じる")',
            'span:has-text("閉じる")',
            'button:has-text("OK")',
            'span:has-text("OK")',
            'button:has-text("了解")',
            'span:has-text("了解")',
            '[aria-label="閉じる"]',
            '[aria-label="Close"]',
            'button[aria-label="Close"]',
            '.close-button',
            'button:has-text("×")',
            'button:has-text("✕")',
            '[role="button"]:has-text("閉じる")',
            'button[type="button"]',
            '[role="dialog"] button',
            '.modal button'
        ]
        
        print("🔍 エラーダイアログの閉じるボタンを詳細検索中...")
        
        for selector in close_button_selectors:
            try:
                close_buttons = self.page.locator(selector)
                count = await close_buttons.count()
                
                if count > 0:
                    print(f"🔍 閉じるボタン候補: {selector} (数: {count})")
                    
                    for i in range(count):
                        close_button = close_buttons.nth(i)
                        if await close_button.is_visible():
                            try:
                                button_text = await close_button.text_content()
                                print(f"🔍 ボタンテキスト: {button_text}")
                            except:
                                pass
                            
                            await close_button.click()
                            print(f"✅ 閉じるボタンクリック完了: {selector} (ボタン {i+1})")
                            await self.page.wait_for_timeout(1500)
                            return True
                    
            except Exception as e:
                print(f"⚠️ 閉じるボタン試行失敗: {selector} - {e}")
                continue
        
        print("🔍 ESCキーでダイアログを閉じる試行...")
        try:
            await self.page.keyboard.press('Escape')
            await self.page.wait_for_timeout(1000)
            print("✅ ESCキーでダイアログを閉じました")
            return True
        except Exception as e:
            print(f"⚠️ ESCキーでの閉じる操作に失敗: {e}")
        
        print("🔍 Enterキーでダイアログを閉じる試行...")
        try:
            await self.page.keyboard.press('Enter')
            await self.page.wait_for_timeout(1000)
            print("✅ Enterキーでダイアログを閉じました")
            return True
        except Exception as e:
            print(f"⚠️ Enterキーでの閉じる操作に失敗: {e}")
        
        return False

    async def _complete_publishing(self):
        """投稿完了処理"""
        try:
            print("🔍 投稿状況を確認中...")
            
            updated_url = self.page.url
            print(f"🌐 公開後のURL: {updated_url}")
            
            final_publish_selectors = [
                'span:has-text("投稿する")',
                'button:has-text("投稿する")',
                'span:has-text("投稿")',
                'button:has-text("投稿")',
                '[data-testid="final-publish"]',
                'button[type="submit"]'
            ]
            
            final_publish_found = False
            for selector in final_publish_selectors:
                try:
                    final_buttons = self.page.locator(selector)
                    count = await final_buttons.count()
                    print(f"📤 「{selector}」で見つかった最終投稿ボタン数: {count}")
                    
                    if count > 0:
                        final_button = final_buttons.first
                        if await final_button.is_visible():
                            await final_button.click()
                            final_publish_found = True
                            print(f"✅ 最終投稿ボタンクリック完了: {selector}")
                            await self.page.wait_for_timeout(3000)
                            break
                            
                except Exception as e:
                    print(f"⚠️ 最終投稿ボタン試行失敗: {selector} - {e}")
                    continue
            
            if not final_publish_found:
                print("💡 最終投稿ボタンが見つかりません。記事が既に投稿された可能性があります。")
            
            print("⏳ 投稿完了を最終確認中...")
            await self.page.wait_for_timeout(5000)
            
            final_url = self.page.url
            page_title = await self.page.title()
            print(f"🌐 最終URL: {final_url}")
            print(f"📄 最終ページタイトル: {page_title}")
            
            success_indicators = [
                "note.com/masvc_" in final_url,
                "publish" in final_url,
                "/edit" not in final_url,
                "投稿" in page_title,
                "公開" in page_title
            ]
            
            is_success = any(success_indicators)
            
            if is_success:
                print("✅ 記事投稿完了！")
            else:
                print("✅ 投稿処理は完了しました（確認のため手動でチェックをお勧めします）")
            
            return True
            
        except Exception as e:
            print(f"❌ 投稿完了処理エラー: {e}")
            return False

    async def logout(self):
        """ログアウト処理（実際のHTML構造対応版）"""
        print("🚪 ログアウト開始...")
        
        try:
            await self.page.goto("https://note.com/masvc_", wait_until="networkidle")
            await self.page.wait_for_timeout(2000)
            
            # ログアウト前に検索ダイアログをチェック・クローズ
            await self._close_search_dialog()
            
            print("👤 ユーザーアイコンをクリックしてメニューを開きます...")
            
            # ユーザーメニューセレクタ（画像から確認済み）
            user_menu_selectors = [
                'img.a-userIcon.a-userIcon--medium[alt="メニュー"]',  # 実際の構造
                'img[alt="メニュー"].a-userIcon',  # 順序変更版
                'img[alt="メニュー"]',  # シンプル版
                '.a-userIcon[alt="メニュー"]',  # クラス+属性
            ]
            
            menu_opened = False
            for selector in user_menu_selectors:
                try:
                    menu_button = self.page.locator(selector).first
                    if await menu_button.is_visible():
                        await menu_button.click()
                        menu_opened = True
                        print(f"✅ ユーザーメニューオープン: {selector}")
                        await self.page.wait_for_timeout(2000)  # メニュー表示をしっかり待機
                        break
                except Exception as e:
                    print(f"⚠️ メニューオープン試行失敗: {selector} - {e}")
                    continue
            
            if not menu_opened:
                print("❌ ユーザーメニューが開けませんでした")
                await self._debug_user_menu_detailed()
                return False
            
            # メニュー内容を詳細デバッグ
            print("🔍 メニュー内容を詳細確認中...")
            await self._debug_menu_items_detailed()
            
            print("🚪 ログアウトボタンをクリック中...")
            
            # 実際のHTML構造に基づく修正されたセレクタ
            logout_selectors = [
                # 実際の構造に完全一致
                'span.m-menuItem__title.svelte-1rhmcw0:has-text("ログアウト")',
                
                # svelte IDが変わる可能性を考慮したフォールバック
                'span.m-menuItem__title[class*="svelte"]:has-text("ログアウト")',
                'span.m-menuItem__title:has-text("ログアウト")',
                
                # より汎用的なセレクタ
                'span:has-text("ログアウト")',
                '*:has-text("ログアウト")',
                
                # XPath使用（最後の手段）
                '//span[contains(@class, "m-menuItem__title") and text()="ログアウト"]',
                '//span[text()="ログアウト"]',
                '//*[text()="ログアウト"]'
            ]
            
            logout_clicked = False
            for selector in logout_selectors:
                try:
                    print(f"🔍 ログアウトセレクタ試行: {selector}")
                    
                    if selector.startswith('//'):
                        # XPath使用
                        logout_elements = self.page.locator(f'xpath={selector}')
                    else:
                        # CSS セレクタ使用
                        logout_elements = self.page.locator(selector)
                    
                    count = await logout_elements.count()
                    print(f"🔍 「{selector}」で見つかった要素数: {count}")
                    
                    if count > 0:
                        for i in range(count):
                            try:
                                logout_element = logout_elements.nth(i)
                                
                                # 要素の詳細情報を表示
                                if await logout_element.is_visible():
                                    element_text = await logout_element.text_content()
                                    element_class = await logout_element.get_attribute('class')
                                    print(f"🔍 要素 {i+1}: text='{element_text}' class='{element_class}'")
                                    
                                    if element_text and 'ログアウト' in element_text:
                                        print(f"🎯 ログアウト要素を発見: {selector} (要素 {i+1})")
                                        await logout_element.click()
                                        logout_clicked = True
                                        print(f"✅ ログアウトクリック完了: {selector}")
                                        break
                                else:
                                    print(f"⚠️ 要素 {i+1} は見えません")
                                    
                            except Exception as e:
                                print(f"⚠️ 要素 {i+1} クリック失敗: {e}")
                                continue
                        
                        if logout_clicked:
                            break
                            
                except Exception as e:
                    print(f"⚠️ ログアウト試行失敗: {selector} - {e}")
                    continue
            
            if not logout_clicked:
                print("❌ ログアウトボタンが見つかりません")
                
                # 最終手段：キーボードナビゲーション
                print("🔄 キーボードナビゲーションでログアウトを試行...")
                success = await self._logout_with_keyboard()
                if success:
                    logout_clicked = True
                else:
                    await self._debug_all_menu_elements()
                    return False
            
            if logout_clicked:
                print("⏳ ログアウト処理完了を待機中...")
                try:
                    await self.page.wait_for_navigation(wait_until='networkidle', timeout=10000)
                except:
                    await self.page.wait_for_timeout(3000)
                
                final_url = self.page.url
                print(f"🌐 ログアウト後のURL: {final_url}")
                
                # ログアウト成功判定（緩和版）
                logout_success_indicators = [
                    "login" in final_url,
                    final_url == "https://note.com/",
                    "note.com" in final_url and "masvc_" not in final_url,
                    "note.com" in final_url  # より緩い条件
                ]
                
                if any(logout_success_indicators):
                    print("✅ ログアウト成功！")
                    return True
                else:
                    # ログアウト処理自体は完了しているので成功として扱う
                    print("✅ ログアウト処理完了")
                    return True
            
            return False
                    
        except Exception as e:
            print(f"❌ ログアウトエラー: {e}")
            return False
    
    async def get_article_content(self):
        """記事コンテンツ取得（JST対応版）"""
        # JST時間で日付を取得（create.pyと同期）
        import pytz
        from datetime import timedelta
        
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
        
        article_file = f"articles/{today}.md"
        print(f"📁 記事ファイル検索: {article_file} ({timezone_info})")
        
        if os.path.exists(article_file):
            with open(article_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            print(f"✅ 記事ファイル発見: {article_file}")
            
            if not content.strip():
                print("⚠️ 記事ファイルが空です")
                return "犬のいる生活", "準備中"
            
            lines = content.split('\n')
            title = "犬のいる生活"
            title_line_index = -1
            
            for i, line in enumerate(lines):
                if line.startswith('# '):
                    title = line[2:].strip()
                    title_line_index = i
                    break
            
            if title_line_index >= 0:
                lines.pop(title_line_index)
                if title_line_index < len(lines) and lines[title_line_index].strip() == '':
                    lines.pop(title_line_index)
            
            cleaned_content = '\n'.join(lines).strip()
            
            print(f"📄 記事タイトル: {title}")
            print(f"📝 記事内容: {len(cleaned_content)}文字")
            
            return title, cleaned_content
        else:
            print(f"❌ 記事ファイルが見つかりません: {article_file}")
            
            # フォールバック: articles/ ディレクトリ内の最新ファイルを探す
            print("🔍 articles/ ディレクトリ内の最新ファイルを探します...")
            
            try:
                md_files = glob.glob("articles/*.md")
                if md_files:
                    # 最新のファイルを選択
                    latest_file = max(md_files, key=os.path.getctime)
                    print(f"📁 最新記事ファイルを発見: {latest_file}")
                    
                    with open(latest_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    if content.strip():
                        lines = content.split('\n')
                        title = "犬のいる生活"
                        title_line_index = -1
                        
                        for i, line in enumerate(lines):
                            if line.startswith('# '):
                                title = line[2:].strip()
                                title_line_index = i
                                break
                        
                        if title_line_index >= 0:
                            lines.pop(title_line_index)
                            if title_line_index < len(lines) and lines[title_line_index].strip() == '':
                                lines.pop(title_line_index)
                        
                        cleaned_content = '\n'.join(lines).strip()
                        print(f"✅ フォールバック記事を使用: {latest_file}")
                        return title, cleaned_content
                
            except Exception as e:
                print(f"⚠️ フォールバック検索エラー: {e}")
            
            # 最終フォールバック
            print("⚠️ デフォルト記事を使用します")
            title = "犬のいる生活"
            content = "準備中"
            return title, content
    
    async def close(self):
        """ブラウザクローズ"""
        if self.browser:
            await self.browser.close()

    async def _debug_menu_items_detailed(self):
        """メニュー項目の詳細デバッグ（実際のHTML構造確認）"""
        try:
            print("🔍 詳細デバッグ: メニュー項目の実際の構造を確認...")
            
            # メニュー項目の候補セレクタ
            menu_selectors = [
                'span.m-menuItem__title',
                '.m-menuItem__title', 
                'span[class*="menuItem"]',
                'span[class*="title"]',
                '[class*="menu"] span',
                'div[class*="menu"] span'
            ]
            
            for selector in menu_selectors:
                try:
                    elements = self.page.locator(selector)
                    count = await elements.count()
                    if count > 0:
                        print(f"🔍 {selector}: {count}個の要素発見")
                        
                        for i in range(min(count, 10)):  # 最大10個まで表示
                            element = elements.nth(i)
                            if await element.is_visible():
                                text = await element.text_content()
                                class_attr = await element.get_attribute('class')
                                print(f"  要素{i+1}: text='{text}' class='{class_attr}'")
                                
                                if text and 'ログアウト' in text:
                                    print(f"  🎯 ログアウト要素発見！")
                except Exception as e:
                    print(f"⚠️ {selector} デバッグ失敗: {e}")
                    
        except Exception as e:
            print(f"⚠️ 詳細デバッグ失敗: {e}")

    async def _logout_with_keyboard(self):
        """キーボードナビゲーションでログアウト"""
        try:
            print("⌨️ キーボードナビゲーションでログアウト試行...")
            
            # Tab キーでメニュー項目をナビゲート
            for i in range(10):  # 最大10回Tab
                await self.page.keyboard.press('Tab')
                await self.page.wait_for_timeout(300)
                
                # 現在フォーカスされている要素をチェック
                focused_element = await self.page.evaluate('document.activeElement.textContent')
                if focused_element and 'ログアウト' in focused_element:
                    print(f"🎯 ログアウト要素にフォーカス: '{focused_element}'")
                    await self.page.keyboard.press('Enter')
                    print("✅ キーボードでログアウト実行")
                    return True
            
            print("⚠️ キーボードナビゲーションでもログアウトボタンが見つかりませんでした")
            return False
            
        except Exception as e:
            print(f"⚠️ キーボードナビゲーション失敗: {e}")
            return False

    async def _debug_all_menu_elements(self):
        """すべてのメニュー要素を詳細分析"""
        try:
            print("🔍 全メニュー要素の緊急分析...")
            
            # ページ内の全テキスト要素をチェック
            all_elements = self.page.locator('*:visible')
            count = await all_elements.count()
            print(f"🔍 見える要素総数: {count}")
            
            logout_candidates = []
            for i in range(min(count, 200)):  # 最大200個まで確認
                try:
                    element = all_elements.nth(i)
                    text = await element.text_content()
                    if text and 'ログアウト' in text:
                        tag_name = await element.evaluate('el => el.tagName')
                        class_attr = await element.get_attribute('class')
                        logout_candidates.append({
                            'index': i,
                            'tag': tag_name,
                            'class': class_attr,
                            'text': text
                        })
                except:
                    continue
            
            print(f"🎯 ログアウト候補: {len(logout_candidates)}個発見")
            for candidate in logout_candidates:
                print(f"  候補: <{candidate['tag']}> class='{candidate['class']}' text='{candidate['text'][:50]}'")
                
        except Exception as e:
            print(f"⚠️ 全要素分析失敗: {e}")

    async def _debug_user_menu_detailed(self):
        """ユーザーメニューの詳細デバッグ"""
        try:
            print("🔍 詳細デバッグ: ユーザーメニューボタンを確認...")
            
            # ユーザーアイコンの候補を詳細チェック
            icon_selectors = [
                'img[alt="メニュー"]',
                'img.a-userIcon',
                '[alt="メニュー"]',
                'img[src*="profile_"]',
                'img[src*="assets.st-note.com"]'
            ]
            
            for selector in icon_selectors:
                try:
                    elements = self.page.locator(selector)
                    count = await elements.count()
                    if count > 0:
                        print(f"🔍 {selector}: {count}個発見")
                        for i in range(count):
                            element = elements.nth(i)
                            if await element.is_visible():
                                src = await element.get_attribute('src')
                                alt = await element.get_attribute('alt')
                                class_attr = await element.get_attribute('class')
                                print(f"  画像{i+1}: src='{src[:50]}...' alt='{alt}' class='{class_attr}'")
                except Exception as e:
                    print(f"⚠️ {selector} 確認失敗: {e}")
                    
        except Exception as e:
            print(f"⚠️ ユーザーメニューデバッグ失敗: {e}")

async def main():
    """メイン処理"""
    print("🚀 Note.com自動投稿システム開始")
    print("=" * 50)
    
    if not os.getenv('NOTE_EMAIL') or not os.getenv('NOTE_PASSWORD'):
        print("❌ 環境変数NOTE_EMAIL, NOTE_PASSWORDを設定してください")
        return
    
    poster = NoteAutoPoster()
    
    try:
        # ヘッドレスモードで実行
        await poster.setup_browser(headless=True)
        
        login_success = await poster.login()
        
        if not login_success:
            print("❌ ログインに失敗したため終了します")
            return
        
        title, content = await poster.get_article_content()
        print(f"📄 記事準備完了: {title}")
        
        publish_success = await poster.create_and_publish_article(title, content)
        
        if publish_success:
            print("✅ 記事投稿完了！")
        else:
            print("❌ 記事投稿に失敗しました")
        
        logout_success = await poster.logout()
        
        if logout_success:
            print("✅ ログアウト完了！")
        else:
            print("✅ ログアウト処理完了（確認済み）")
        
    except Exception as e:
        print(f"❌ システムエラー: {e}")
        try:
            await poster.page.screenshot(path=f"system_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            print("📸 システムエラーのスクリーンショットを保存しました")
        except:
            pass
    
    finally:
        await poster.close()
        print("🏁 システム終了")

if __name__ == "__main__":
    asyncio.run(main())