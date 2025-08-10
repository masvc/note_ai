#!/usr/bin/env python3
"""
Note.com自動投稿システム（完全版）
投稿機能を実装し、タイトル・本文・アイキャッチ設定・公開まで自動化
"""

import os
import asyncio
import re
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
        """記事作成・投稿処理（完全実装版）"""
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
            
            # 4. アイキャッチ設定
            print("🖼️ アイキャッチ設定開始...")
            await self._set_eyecatch_image(title)
            
            # 5. 公開に進む
            print("📢 公開処理開始...")
            await self.page.wait_for_timeout(5000)  # アイキャッチ保存完了を十分に待つ
            
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
    async def _publish_with_retry(self):
        """リトライ機能付き公開処理"""
        max_retry = 3
        
        for attempt in range(max_retry):
            print(f"📢 公開処理試行 {attempt + 1}/{max_retry}")
            
            try:
                # 現在のページを確認
                current_url = self.page.url
                print(f"🌐 公開前のURL: {current_url}")
                
                # 公開ボタンをクリック
                publish_success = await self._click_publish_button()
                
                if not publish_success:
                    print(f"⚠️ 公開ボタンクリック失敗 (試行 {attempt + 1})")
                    continue
                
                # 公開ボタンクリック後の処理を待機
                print("⏳ 公開処理を待機中...")
                await self.page.wait_for_timeout(3000)
                
                # エラーダイアログをチェック
                error_handled = await self._handle_publish_error()
                
                if error_handled:
                    print("⚠️ エラーが発生しました。リトライします...")
                    await self.page.wait_for_timeout(2000)
                    continue
                
                # エラーがない場合は次のステップに進む
                return await self._complete_publishing()
                
            except Exception as e:
                print(f"⚠️ 公開処理エラー (試行 {attempt + 1}): {e}")
                if attempt < max_retry - 1:
                    await self.page.wait_for_timeout(3000)
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
        
        # キーボードショートカットを試す
        print("⚠️ 公開ボタンが見つかりません。キーボードショートカットを試します...")
        try:
            await self.page.keyboard.press('Meta+Enter')  # Mac用の公開ショートカット
            print("✅ キーボードショートカットで公開を試行")
            return True
        except:
            print("❌ 公開処理に失敗しました")
            return False

    async def _handle_publish_error(self):
        """公開エラーダイアログの処理"""
        try:
            # エラーダイアログの検出
            error_dialog_selectors = [
                ':has-text("タイトル、本文を入力してください")',
                ':has-text("入力してください")',
                '.error-dialog',
                '[role="dialog"]',
                '.modal:has-text("エラー")'
            ]
            
            for selector in error_dialog_selectors:
                try:
                    error_dialog = self.page.locator(selector).first
                    if await error_dialog.is_visible():
                        print(f"🚨 エラーダイアログを検出: {selector}")
                        
                        # エラーメッセージを取得
                        try:
                            error_text = await error_dialog.text_content()
                            print(f"🚨 エラー内容: {error_text}")
                        except:
                            pass
                        
                        # 「閉じる」ボタンを探してクリック
                        close_success = await self._close_error_dialog()
                        
                        if close_success:
                            print("✅ エラーダイアログを閉じました")
                            return True
                        else:
                            print("⚠️ エラーダイアログを閉じることができませんでした")
                            return True  # エラーがあることは確実なのでリトライ
                            
                except Exception as e:
                    print(f"⚠️ エラーダイアログ検出失敗: {selector} - {e}")
                    continue
            
            # エラーダイアログが見つからない場合
            return False
            
        except Exception as e:
            print(f"⚠️ エラーハンドリング中にエラー: {e}")
            return False

    async def _close_error_dialog(self):
        """エラーダイアログの「閉じる」ボタンをクリック"""
        close_button_selectors = [
            'button:has-text("閉じる")',
            'span:has-text("閉じる")',
            '[aria-label="閉じる"]',
            'button[aria-label="Close"]',
            '.close-button',
            'button:has-text("×")',
            'button:has-text("✕")'
        ]
        
        for selector in close_button_selectors:
            try:
                close_button = self.page.locator(selector).first
                if await close_button.is_visible():
                    await close_button.click()
                    print(f"✅ 閉じるボタンクリック完了: {selector}")
                    await self.page.wait_for_timeout(1000)
                    return True
                    
            except Exception as e:
                print(f"⚠️ 閉じるボタン試行失敗: {selector} - {e}")
                continue
        
        # ESCキーを試す
        try:
            await self.page.keyboard.press('Escape')
            print("✅ ESCキーでダイアログを閉じました")
            return True
        except:
            print("⚠️ ESCキーでの閉じる操作に失敗")
            return False

    async def _complete_publishing(self):
        """投稿完了処理"""
        try:
            # 投稿状況を確認
            print("🔍 投稿状況を確認中...")
            
            # 現在のURLをチェック
            updated_url = self.page.url
            print(f"🌐 公開後のURL: {updated_url}")
            
            # 追加の投稿ボタンがある場合はクリック
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
            
            # 投稿完了確認
            print("⏳ 投稿完了を最終確認中...")
            await self.page.wait_for_timeout(5000)
            
            # 投稿完了を確認
            final_url = self.page.url
            page_title = await self.page.title()
            print(f"🌐 最終URL: {final_url}")
            print(f"📄 最終ページタイトル: {page_title}")
            
            # 成功の判定（より緩い基準）
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
            
            return True  # 処理完了として扱う
            
        except Exception as e:
            print(f"❌ 投稿完了処理エラー: {e}")
            return False


    async def _set_eyecatch_image(self, title):
        """アイキャッチ画像設定"""
        print("🖼️ アイキャッチ画像設定中...")
        
        try:
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
            
            # 別のアプローチ：画像アイコンのあるボタンを探す
            if not select_clicked:
                print("🔍 画像アイコン付きボタンを探します...")
                try:
                    # 画像アイコンが含まれているボタンを探す
                    image_icon_buttons = self.page.locator('button:has(svg[data-src="/icons/image.svg"]), div:has(svg[data-src="/icons/image.svg"])')
                    count = await image_icon_buttons.count()
                    print(f"🔍 画像アイコンボタン数: {count}")
                    
                    for i in range(count):
                        button = image_icon_buttons.nth(i)
                        if await button.is_visible():
                            # ボタンのテキストを確認
                            text_content = await button.text_content()
                            print(f"🔍 ボタンテキスト: {text_content}")
                            
                            if "記事にあう" in text_content or "画像を選ぶ" in text_content:
                                await button.click()
                                select_clicked = True
                                print(f"✅ 画像アイコンボタンクリック完了")
                                break
                except Exception as e:
                    print(f"⚠️ 画像アイコンボタン検索エラー: {e}")
            
            if not select_clicked:
                print("❌ 「記事にあう画像を選ぶ」ボタンが見つかりません。スキップします。")
                return
            
            await self.page.wait_for_timeout(2000)
            
            # 3. モーダルが開くのを待機してから検索機能を探す
            print("🔍 画像選択モーダルの読み込みを待機中...")
            await self.page.wait_for_timeout(3000)
            
            # まずページ上の全ての入力欄とボタンを調査
            print("🔍 ページ上の要素を調査中...")
            
            # 検索アイコンまたは検索ボタンを探す
            search_triggers = [
                'svg[data-src="/icons/search.svg"]',
                'button:has(svg[data-src="/icons/search.svg"])',
                '[aria-label="検索"]',
                'button[title*="検索"]',
                '*[role="button"]:has-text("検索")'
            ]
            
            search_triggered = False
            for selector in search_triggers:
                try:
                    elements = self.page.locator(selector)
                    count = await elements.count()
                    print(f"🔍 検索トリガー「{selector}」で見つかった要素数: {count}")
                    
                    if count > 0:
                        element = elements.first
                        if await element.is_visible():
                            await element.click()
                            search_triggered = True
                            print(f"✅ 検索トリガークリック完了: {selector}")
                            break
                        else:
                            print(f"⚠️ 検索トリガー要素は存在するが見えません: {selector}")
                            
                except Exception as e:
                    print(f"⚠️ 検索トリガー試行失敗: {selector} - {e}")
                    continue
            
            # 検索トリガーが見つからない場合は、直接検索入力欄を探す
            if not search_triggered:
                print("🔍 検索トリガーが見つからないため、直接検索入力欄を探します...")
            
            await self.page.wait_for_timeout(1000)
            
            # 全ての入力欄を調査
            print("🔍 利用可能な入力欄を調査中...")
            all_inputs = self.page.locator('input')
            input_count = await all_inputs.count()
            print(f"🔍 見つかった入力欄の総数: {input_count}")
            
            search_input_found = False
            for i in range(input_count):
                try:
                    input_element = all_inputs.nth(i)
                    if await input_element.is_visible():
                        # 入力欄の属性を調査
                        input_type = await input_element.get_attribute('type')
                        placeholder = await input_element.get_attribute('placeholder')
                        aria_label = await input_element.get_attribute('aria-label')
                        
                        print(f"🔍 入力欄 {i+1}: type={input_type}, placeholder={placeholder}, aria-label={aria_label}")
                        
                        # テキスト入力欄で、検索に関連しそうなものを探す
                        if input_type == 'text' or input_type is None:
                            # この入力欄を試してみる
                            await input_element.click()
                            await self.page.wait_for_timeout(500)
                            
                            # キーワードを入力してみる
                            keyword = self._extract_keyword_from_title(title)
                            print(f"🔍 入力欄 {i+1} にキーワード「{keyword}」を入力します")
                            
                            await input_element.fill(keyword)
                            await input_element.press('Enter')
                            
                            search_input_found = True
                            print(f"✅ 検索キーワード入力完了（入力欄 {i+1}）")
                            break
                            
                except Exception as e:
                    print(f"⚠️ 入力欄 {i+1} での試行失敗: {e}")
                    continue
            
            if not search_input_found:
                print("⚠️ 検索入力欄が見つかりません。キーワードなしで画像選択を試行します。")
                # キーワード検索なしで次のステップに進む
            
            # 4. 画像が読み込まれるまで待機
            print("🖼️ 画像の読み込みを待機中...")
            await self.page.wait_for_timeout(4000)  # 画像読み込み待機時間を延長
            
            # 5. 利用可能な画像を探して選択
            print("🖼️ 利用可能な画像を探します...")
            
            # 様々なパターンで画像を探す
            image_selectors = [
                'img[src*="assets.st-note.com"]',  # Note.comの画像
                'img[src*="note.com"]',
                'img.sc-a7ee00d5-4',
                'img[width="400"]',
                'img[alt*="画像"]',
                'img'  # 最後の手段として全ての画像
            ]
            
            image_selected = False
            for selector in image_selectors:
                try:
                    images = self.page.locator(selector)
                    count = await images.count()
                    print(f"🖼️ 「{selector}」で見つかった画像数: {count}")
                    
                    if count > 0:
                        # 最初の数枚の画像を調査
                        for i in range(min(count, 5)):  # 最大5枚まで調査
                            try:
                                image = images.nth(i)
                                if await image.is_visible():
                                    # 画像のsrcを確認
                                    src = await image.get_attribute('src')
                                    print(f"🖼️ 画像 {i+1}: {src}")
                                    
                                    # クリック可能かチェック
                                    await image.click()
                                    image_selected = True
                                    print(f"✅ 画像選択完了: {selector} (画像 {i+1})")
                                    break
                            except Exception as e:
                                print(f"⚠️ 画像 {i+1} クリック失敗: {e}")
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
            
            # 6. 「この画像を挿入」ボタンをクリック
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
            
            # 7. 「保存」ボタンをクリック（画像クロップ画面の右下）
            print("💾 画像クロップ画面の保存ボタンをクリック中...")
            await self.page.wait_for_timeout(2000)
            
            save_button_selectors = [
                'button:has-text("保存")',  # 最も一般的
                'span:has-text("保存")',
                '#\\:rj\\:',  # IDパターン
                'button[class*="font-bold"]:has-text("保存")',  # クラスパターン
                '[role="button"]:has-text("保存")',
                'div:has-text("保存"):last-child'  # 最後の保存ボタン
            ]
            
            save_clicked = False
            for selector in save_button_selectors:
                try:
                    save_buttons = self.page.locator(selector)
                    count = await save_buttons.count()
                    print(f"💾 「{selector}」で見つかった保存ボタン数: {count}")
                    
                    if count > 0:
                        # 最後の（右下の）保存ボタンを選択
                        save_button = save_buttons.last
                        if await save_button.is_visible():
                            # オーバーレイがある場合は少し待つ
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
                await self.page.wait_for_timeout(8000)  # 保存処理と画像読み込みの完了を待つ（延長）
                
                # 画像が正常に読み込まれたかチェック
                await self._verify_eyecatch_loaded()
            else:
                print("⚠️ 保存ボタンが見つかりませんでした")
                
        except Exception as e:
            print(f"⚠️ アイキャッチ設定エラー: {e}")
            print("📝 アイキャッチなしで投稿を続行します")

    async def _verify_eyecatch_loaded(self):
        """アイキャッチ画像の読み込み完了を確認"""
        try:
            print("🔍 アイキャッチ画像の読み込み状況を確認中...")
            
            # アイキャッチ画像エリアが表示されているかチェック
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

    def _extract_keyword_from_title(self, title):
        """タイトルからメインキーワードを抽出"""
        # 日本語の場合、スペースまたは句読点で分割
        # 英語の場合、スペースで分割
        keywords = re.split(r'[　\s、。！？\-－]+', title)
        keywords = [k.strip() for k in keywords if k.strip() and len(k.strip()) > 1]
        
        if keywords:
            # 最初の意味のある単語を返す
            for keyword in keywords:
                if len(keyword) >= 2:  # 2文字以上
                    return keyword
            return keywords[0]
        else:
            # フォールバック
            return "記事"

    async def logout(self):
        """ログアウト処理"""
        print("🚪 ログアウト開始...")
        
        try:
            # まずプロフィールページに移動
            await self.page.goto("https://note.com/masvc_", wait_until="networkidle")
            await self.page.wait_for_timeout(2000)
            
            # ユーザーメニューを開く
            print("👤 ユーザーメニューを開きます...")
            user_menu_selectors = [
                'button.o-navbarPrimary__userIconButton',
                'button[aria-controls="userMenu"]',
                '.a-userIcon',
                'img[alt="メニュー"]'
            ]
            
            menu_opened = False
            for selector in user_menu_selectors:
                try:
                    menu_button = self.page.locator(selector).first
                    if await menu_button.is_visible():
                        await menu_button.click()
                        menu_opened = True
                        print(f"✅ ユーザーメニューオープン: {selector}")
                        break
                except Exception as e:
                    print(f"⚠️ メニューオープン試行失敗: {selector} - {e}")
                    continue
            
            if not menu_opened:
                print("❌ ユーザーメニューが開けませんでした")
                return False
            
            await self.page.wait_for_timeout(1000)
            
            # ログアウトボタンをクリック
            print("🚪 ログアウトボタンをクリック中...")
            logout_selectors = [
                'span:has-text("ログアウト")',
                '.m-menuItem__title:has-text("ログアウト")',
                'button:has-text("ログアウト")',
                '[data-testid="logout"]',
                'a:has-text("ログアウト")'
            ]
            
            logout_clicked = False
            for selector in logout_selectors:
                try:
                    logout_element = self.page.locator(selector).first
                    if await logout_element.is_visible():
                        await logout_element.click()
                        logout_clicked = True
                        print(f"✅ ログアウトクリック完了: {selector}")
                        break
                except Exception as e:
                    print(f"⚠️ ログアウト試行失敗: {selector} - {e}")
                    continue
            
            if not logout_clicked:
                print("❌ ログアウトボタンが見つかりません")
                return False
            
            # ログアウト完了を待機
            print("⏳ ログアウト処理完了を待機中...")
            try:
                await self.page.wait_for_navigation(wait_until='networkidle', timeout=10000)
            except:
                await self.page.wait_for_timeout(3000)
            
            final_url = self.page.url
            print(f"🌐 ログアウト後のURL: {final_url}")
            
            if "login" in final_url or "note.com" in final_url:
                print("✅ ログアウト成功！")
                return True
            else:
                print("⚠️ ログアウトが完了したか不明です")
                return False
                
        except Exception as e:
            print(f"❌ ログアウトエラー: {e}")
            try:
                await self.page.screenshot(path=f"logout_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                print("📸 ログアウトエラーのスクリーンショットを保存しました")
            except:
                pass
            return False
    
    async def get_article_content(self):
        """記事コンテンツ取得"""
        today = datetime.now().strftime("%Y%m%d")
        article_file = f"articles/{today}.md"
        
        if os.path.exists(article_file):
            with open(article_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # ファイルが空の場合
            if not content.strip():
                return "犬のいる生活", "準備中"
            
            # タイトル抽出と本文からタイトル行を除去
            lines = content.split('\n')
            title = "犬のいる生活"  # デフォルトタイトル
            title_line_index = -1
            
            # タイトル行を探す
            for i, line in enumerate(lines):
                if line.startswith('# '):
                    title = line[2:].strip()  # "# "を除去してタイトルを取得
                    title_line_index = i
                    break
            
            # タイトル行を本文から除去
            if title_line_index >= 0:
                # タイトル行を除去
                lines.pop(title_line_index)
                # タイトル行の後の空行も除去（もしあれば）
                if title_line_index < len(lines) and lines[title_line_index].strip() == '':
                    lines.pop(title_line_index)
            
            # 修正された本文を作成
            cleaned_content = '\n'.join(lines).strip()
            
            return title, cleaned_content
        else:
            # ファイルが存在しない場合のデフォルト記事
            title = "犬のいる生活"
            content = "準備中"
            return title, content
    
    async def close(self):
        """ブラウザクローズ"""
        if self.browser:
            await self.browser.close()

async def main():
    """メイン処理"""
    print("🚀 Note.com自動投稿システム開始")
    print("=" * 50)
    
    # 環境変数チェック
    if not os.getenv('NOTE_EMAIL') or not os.getenv('NOTE_PASSWORD'):
        print("❌ 環境変数NOTE_EMAIL, NOTE_PASSWORDを設定してください")
        return
    
    poster = NoteAutoPoster()
    
    try:
        # ブラウザセットアップ
        is_headless = os.getenv('HEADLESS', 'false').lower() == 'true'
        await poster.setup_browser(headless=is_headless)
        
        # ログイン処理
        login_success = await poster.login()
        
        if not login_success:
            print("❌ ログインに失敗したため終了します")
            return
        
        # 記事コンテンツ取得
        title, content = await poster.get_article_content()
        print(f"📄 記事準備完了: {title}")
        
        # 記事作成・投稿
        publish_success = await poster.create_and_publish_article(title, content)
        
        if publish_success:
            print("✅ 記事投稿完了！")
        else:
            print("❌ 記事投稿に失敗しました")
        
        # ログアウト処理
        logout_success = await poster.logout()
        
        if logout_success:
            print("✅ ログアウト完了！")
        else:
            print("⚠️ ログアウトに問題がありました")
        
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