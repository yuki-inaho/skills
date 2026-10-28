#!/usr/bin/env python3
"""Live browser probe using only a newly generated, anonymous 4096-byte payload.

No arbitrary input files, accounts, email, original data, or persistent profiles.
Private receipts are separate from public evidence. Stop on challenges/errors.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import secrets
import string
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as BrowserTimeout


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    with temp.open('w', encoding='utf-8') as f:
        os.chmod(temp, 0o600)
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n'); f.flush(); os.fsync(f.fileno())
    os.replace(temp, path)
    assert json.loads(path.read_text()) == data


def controls(page):
    return page.locator('input,button,a').evaluate_all('els=>els.map(e=>({tag:e.tagName,id:e.id,type:e.type||null,text:(e.innerText||e.value||e.title||e.getAttribute("aria-label")||"").slice(0,500),href:e.getAttribute("href")}))')


def challenge(page):
    text = page.locator('body').inner_text()
    return bool(re.search(r'verify you are human|checking your browser|captcha|access denied|自動アクセス|ロボットではない', text, re.I))


def close_ad(page):
    button = page.get_by_role('button', name='×', exact=True)
    if button.count() == 1 and button.is_visible():
        button.click(timeout=2000)


def run(root: Path, chrome: str | None) -> dict:
    root.mkdir(parents=True, exist_ok=False)
    private = root/'private'; private.mkdir(mode=0o700)
    public = root/'public'; public.mkdir()
    filename = secrets.token_hex(16)+'.bin'
    payload = secrets.token_bytes(4096)
    source = private/filename; source.write_bytes(payload)
    password = ''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(4))
    report = {'scope':'live','provider':'gigafile','file_name':filename,'bytes':len(payload),
              'sha256':hashlib.sha256(payload).hexdigest(),'status':'incomplete','steps':[],
              'no_real_data':True,'real_service_uploads':0,'cleanup':'minimum observed expiry; no automatic deletion'}
    receipt = {'file_name':filename,'password':password,'share_url':None,'events':[]}
    current = None
    def save(label):
        report['steps'].append(label); receipt['events'].append(label)
        write_json(private/'receipt.private.json',receipt)
        write_json(public/'live-summary.json',report)
    save('synthetic_payload_prepared')
    try:
        with sync_playwright() as p:
            options={'headless':True}
            if chrome: options['executable_path']=chrome
            else: options['channel']='chrome'
            browser=p.chromium.launch(**options)
            uploader=browser.new_context(accept_downloads=True)
            page=uploader.new_page();current=page
            page.goto('https://gigafile.nu/',wait_until='domcontentloaded',timeout=30000)
            if challenge(page):raise RuntimeError('Human verification or access block; no retry')
            close_ad(page)
            # This visible option was found on the public landing page during the read-only probe.
            duration=page.get_by_text('3日',exact=True)
            if duration.count()==1:duration.click(timeout=5000)
            receipt['requested_retention_days']=3
            if page.locator('input[type=file]').count()!=1:
                raise RuntimeError('Upload input is not unique; inspect before continuing')
            page.locator('input[type=file]').set_input_files(str(source))
            report['real_service_uploads']=1
            page.wait_for_function("() => [...document.querySelectorAll('input')].some(e=>/^https:\/\/(?:[0-9]+\.)?gigafile\.nu\/[0-9]{4}-[A-Za-z0-9_-]{12,128}$/.test(e.value))",timeout=60000)
            found=[x for x in controls(page) if re.fullmatch(r'https://(?:[0-9]+\.)?gigafile\.nu/[0-9]{4}-[A-Za-z0-9_-]{12,128}',x['text'] or '') and x['tag']=='INPUT']
            urls=sorted({x['text'] for x in found})
            if len(urls)!=1:raise RuntimeError('Share URL is missing or ambiguous')
            receipt['share_url']=urls[0]
            receipt['url_source']='input_value'
            receipt['upload_text']=page.locator('body').inner_text()
            if filename not in receipt['upload_text']:raise RuntimeError('Uploaded filename not present')
            write_json(private/'upload-controls.json',{'controls':controls(page)})
            save('upload_confirmed_url_persisted_before_navigation')
            # Locate the password control in the smallest ancestor of the observed URL input.
            item=next(x for x in found if x['text']==urls[0])
            if not item['id']:raise RuntimeError('URL input lacks a stable id')
            url_input=page.locator('[id='+json.dumps(item['id'])+']')
            row=url_input
            for _ in range(8):
                row=row.locator('xpath=..')
                if row.get_by_text('設定',exact=True).count()==1 and 'ダウンロードパスワード' in row.inner_text():break
            else:raise RuntimeError('Password row not identified')
            receipt['row_html']=row.evaluate('e=>e.outerHTML')
            inputs=row.locator('input[type=text],input[type=password]')
            candidates=[]
            for j in range(inputs.count()):
                el=inputs.nth(j)
                if el.is_visible() and el.get_attribute('id')!=item['id'] and el.get_attribute('maxlength')=='4':candidates.append(el)
            if len(candidates)!=1:raise RuntimeError('Password field not unique')
            dialogs=[]
            def dialog_handler(dialog):
                dialogs.append(dialog.message)
                if 'ダウンロードキーを設定しました' in dialog.message:dialog.accept()
                else:dialog.dismiss()
            page.on('dialog',dialog_handler)
            candidates[0].fill(password)
            row.get_by_text('設定',exact=True).click(timeout=10000)
            # Observe a UI confirmation; a filled input alone is never sufficient.
            end=time.monotonic()+5
            while time.monotonic()<end:
                if any('ダウンロードキーを設定しました' in d for d in dialogs):break
                if 'ダウンロードキーを設定しました' in page.locator('body').inner_text():break
                page.wait_for_timeout(100)
            else:raise RuntimeError('No password-set confirmation')
            receipt['password_confirmation']='ダウンロードキーを設定しました'
            receipt['expiry_text']=row.inner_text()
            save('password_configuration_confirmed')
            page.screenshot(path=str(private/'upload.png'),full_page=False)
            uploader.close()
            receipt=json.loads((private/'receipt.private.json').read_text())
            recipient=browser.new_context(accept_downloads=True)
            page=recipient.new_page();current=page
            page.goto(receipt['share_url'],wait_until='domcontentloaded',timeout=30000)
            if challenge(page):raise RuntimeError('Recipient challenge; stop')
            close_ad(page)
            if filename not in page.locator('body').inner_text():raise RuntimeError('Recipient filename mismatch')
            receipt['recipient_url']=page.url
            receipt['recipient_text']=page.locator('body').inner_text()
            write_json(private/'recipient-controls.json',{'controls':controls(page)})
            save('fresh_recipient_page_verified')
            # Identify by observed DOM semantics, never choose an advertisement download link.
            pw_inputs=page.locator('input').filter(visible=True)
            picks=[]
            for j in range(pw_inputs.count()):
                el=pw_inputs.nth(j)
                if 'dlkey' in (el.get_attribute('id') or '') or 'dlkey' in (el.get_attribute('name') or ''):picks.append(el)
            if len(picks)!=1:raise RuntimeError('Recipient password field not identified')
            pw_input=picks[0]
            button=page.get_by_role('button',name='ダウンロード開始',exact=True)
            if button.count()!=1:
                button=page.get_by_text('ダウンロード開始',exact=True)
            if button.count()!=1:raise RuntimeError('Download control not unique')
            recipient_dialogs=[]
            def deny_dialog(dialog):recipient_dialogs.append(dialog.message);dialog.dismiss()
            page.on('dialog',deny_dialog)
            for label,value in [('missing',''),('wrong','0'*4 if password!='0'*4 else '1'*4)]:
                pw_input.fill(value);before=len(recipient_dialogs)
                try:
                    with page.expect_download(timeout=3500) as event:button.click(timeout=5000)
                    unexpected=event.value
                    unexpected.cancel()
                    raise RuntimeError('Download allowed with '+label+' password')
                except BrowserTimeout:
                    observed='\n'.join(recipient_dialogs[before:])+'\n'+page.locator('body').inner_text()
                    if not re.search(r'キー.*(異な|違|入力)|パスワード.*(異な|違|入力)|認証.*失敗',observed):
                        raise RuntimeError('No explicit denial for '+label+' password')
                receipt[label+'_password_denied']=True;save(label+'_password_rejected')
            pw_input.fill(password)
            with page.expect_download(timeout=30000) as event:button.click(timeout=5000)
            download=event.value
            if download.failure():raise RuntimeError('Browser reported download failure')
            target=private/'downloaded.bin';download.save_as(str(target))
            received=target.read_bytes()
            if received!=payload:raise RuntimeError('Downloaded bytes differ')
            if download.suggested_filename!=filename:raise RuntimeError('Downloaded filename differs')
            receipt['downloaded_sha256']=hashlib.sha256(received).hexdigest()
            receipt['downloaded_bytes']=len(received)
            receipt['suggested_filename']=download.suggested_filename
            save('download_bytes_name_and_sha256_verified')
            # Screenshot is kept private because the DOM contains a share capability.
            page.screenshot(path=str(private/'recipient.png'),full_page=False)
            recipient.close();browser.close()
            saved=json.loads((private/'receipt.private.json').read_text())
            assert saved['share_url'] and saved['password'] and saved['downloaded_sha256']==report['sha256']
            (private/'handoff.private.txt').write_text('URL: '+saved['share_url']+'\nPassword: '+saved['password']+'\n',encoding='utf-8')
            os.chmod(private/'handoff.private.txt',0o600)
            report['status']='passed';save('handoff_restored_from_disk_after_browser_closed')
    except Exception as e:
        report['status']='blocked' if 'challenge' in str(e).lower() or 'verification' in str(e).lower() else 'failed'
        error=str(e)
        for value in [password,receipt.get('share_url')]:
            if value:error=error.replace(value,'[REDACTED]')
        report['error']=error[:1200]
        # Private observations are useful for diagnosing DOM changes without exposing tokens.
        try:
            if current and not current.is_closed():
                write_json(private/'failure-controls.json',{'controls':controls(current),'text':current.locator('body').inner_text()})
        except Exception:pass
        save('stopped_without_claiming_completion')
    return report

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--chromium');ap.add_argument('--allow-synthetic-live-upload',action='store_true')
    a=ap.parse_args()
    if not a.allow_synthetic_live_upload:ap.error('Explicit opt-in for one anonymous synthetic upload is required')
    result=run(a.output,a.chromium)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result['status']=='passed' else 1)
