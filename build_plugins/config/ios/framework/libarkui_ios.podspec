#
# NOTE: This podspec is NOT to be published. It is only used as a local source!
#

Pod::Spec.new do |s|
  s.name             = 'libarkui_ios'
  s.version          = '1.0.0'
  s.summary          = 'The ArkUI-X project extends the ArkUI framework to multiple OS platforms.'
  s.description      = <<-DESC
  The ArkUI-X project extends the ArkUI framework to multiple OS platforms.
  This enables developers to use one main set of code to develop applications for multiple OS platforms.
                       DESC
  s.homepage         = 'https://arkui-x.cn'
  s.license          = { :type => 'Apache' }
  s.author           = { 'ArkUI Dev Team' => 'contact@mail.arkui-x.cn' }
  s.source           = { :git => 'https://gitee.com/arkui-x', :tag => s.version.to_s }
  s.ios.deployment_target = '8.0'
  s.vendored_frameworks = 'libarkui_ios.framework'
end
