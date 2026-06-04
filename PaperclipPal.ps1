Add-Type -AssemblyName PresentationFramework
Add-Type -AssemblyName PresentationCore
Add-Type -AssemblyName WindowsBase

$ErrorActionPreference = 'Stop'

[System.Threading.Thread]::CurrentThread.CurrentCulture = [System.Globalization.CultureInfo]::InvariantCulture
[System.Threading.Thread]::CurrentThread.CurrentUICulture = [System.Globalization.CultureInfo]::InvariantCulture

$xaml = @'
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Width="260" Height="300"
        WindowStyle="None"
        ResizeMode="NoResize"
        AllowsTransparency="True"
        Background="Transparent"
        Topmost="True"
        ShowInTaskbar="False"
        WindowStartupLocation="Manual">
  <Canvas x:Name="Root" Width="260" Height="300" Background="Transparent" RenderTransformOrigin="0.5,0.5">
    <Canvas.RenderTransform>
      <TransformGroup>
        <ScaleTransform x:Name="BounceScale" ScaleX="1" ScaleY="1"/>
        <TranslateTransform x:Name="IdleBob" X="0" Y="0"/>
      </TransformGroup>
    </Canvas.RenderTransform>

    <Canvas x:Name="Body" Width="260" Height="300" RenderTransformOrigin="0.5,0.58">
      <Canvas.RenderTransform>
        <TransformGroup>
          <RotateTransform x:Name="BodyTilt" Angle="0"/>
          <TranslateTransform x:Name="BodyShift" X="0" Y="0"/>
      </TransformGroup>
    </Canvas.RenderTransform>

      <Canvas.Resources>
        <SolidColorBrush x:Key="WireMainBrush" Color="#A6A8A9"/>
        <SolidColorBrush x:Key="EyeBrush" Color="#FFFFFF"/>
      </Canvas.Resources>

      <Canvas x:Name="Wire" Width="260" Height="300" RenderTransformOrigin="0.48,0.58">
        <Canvas.RenderTransform>
          <TransformGroup>
            <RotateTransform x:Name="WireTilt" Angle="0"/>
            <TranslateTransform x:Name="WireShift" X="0" Y="0"/>
          </TransformGroup>
        </Canvas.RenderTransform>

        <Path x:Name="OuterClip" Stroke="{StaticResource WireMainBrush}" StrokeThickness="18" StrokeStartLineCap="Round"
              StrokeEndLineCap="Round" StrokeLineJoin="Round" Fill="Transparent"
              Data="M 68 125 C 67 82 96 57 130 63 C 162 69 181 96 178 130"/>
        <Path Stroke="{StaticResource WireMainBrush}" StrokeThickness="18" StrokeStartLineCap="Round"
              StrokeEndLineCap="Round" StrokeLineJoin="Round" Fill="Transparent"
              Data="M 67 124 L 62 181 C 59 216 69 239 93 249 C 122 260 151 246 158 222"/>

        <Path Stroke="{StaticResource WireMainBrush}" StrokeThickness="17" StrokeStartLineCap="Round"
              StrokeEndLineCap="Round" StrokeLineJoin="Round" Fill="Transparent"
              Data="M 126 150 L 126 202 C 126 224 138 239 155 238 C 174 237 181 220 181 202"/>

        <Path Stroke="{StaticResource WireMainBrush}" StrokeThickness="16" StrokeStartLineCap="Round"
              StrokeEndLineCap="Round" StrokeLineJoin="Round" Fill="Transparent"
              Data="M 181 202 C 181 219 174 233 158 239"/>
        <Path Stroke="{StaticResource WireMainBrush}" StrokeThickness="17" StrokeStartLineCap="Round"
              StrokeEndLineCap="Round" StrokeLineJoin="Round" Fill="Transparent"
              Data="M 181 201 C 190 181 201 164 211 157"/>
      </Canvas>

      <Ellipse x:Name="LeftEye" Canvas.Left="58" Canvas.Top="98" Width="58" Height="57" Fill="{StaticResource EyeBrush}" RenderTransformOrigin="0.5,0.5">
        <Ellipse.RenderTransform>
          <ScaleTransform x:Name="LeftBlink" ScaleX="1" ScaleY="1"/>
        </Ellipse.RenderTransform>
      </Ellipse>
      <Ellipse x:Name="RightEye" Canvas.Left="119" Canvas.Top="110" Width="58" Height="57" Fill="{StaticResource EyeBrush}" RenderTransformOrigin="0.5,0.5">
        <Ellipse.RenderTransform>
          <ScaleTransform x:Name="RightBlink" ScaleX="1" ScaleY="1"/>
        </Ellipse.RenderTransform>
      </Ellipse>
      <Ellipse x:Name="LeftPupil" Canvas.Left="77" Canvas.Top="115" Width="31" Height="31" Fill="#3A2734" RenderTransformOrigin="0.5,0.5">
        <Ellipse.RenderTransform>
          <ScaleTransform x:Name="LeftPupilBlink" ScaleX="1" ScaleY="1"/>
        </Ellipse.RenderTransform>
      </Ellipse>
      <Ellipse x:Name="RightPupil" Canvas.Left="139" Canvas.Top="128" Width="31" Height="31" Fill="#3A2734" RenderTransformOrigin="0.5,0.5">
        <Ellipse.RenderTransform>
          <ScaleTransform x:Name="RightPupilBlink" ScaleX="1" ScaleY="1"/>
        </Ellipse.RenderTransform>
      </Ellipse>
      <Path x:Name="LeftBrow" Stroke="#4B3029" StrokeThickness="9" StrokeStartLineCap="Round"
            StrokeEndLineCap="Round" Fill="Transparent"
            Data="M 51 79 C 68 70 88 72 105 81"/>
      <Path x:Name="RightBrow" Stroke="#4B3029" StrokeThickness="9" StrokeStartLineCap="Round"
            StrokeEndLineCap="Round" Fill="Transparent"
            Data="M 123 88 C 140 84 160 88 181 101"/>

      <Border x:Name="Bubble" Canvas.Left="14" Canvas.Top="230" Width="232" MinHeight="44"
              CornerRadius="12" Background="#FDFDFD" BorderBrush="#D4DEE8" BorderThickness="1"
              Visibility="Collapsed" Opacity="0.94">
        <TextBlock x:Name="BubbleText" Padding="12,8" FontFamily="Segoe UI" FontSize="13"
                   TextWrapping="Wrap" Foreground="#202932"/>
      </Border>
    </Canvas>
  </Canvas>
</Window>
'@

$reader = New-Object System.Xml.XmlNodeReader ([xml]$xaml)
$window = [Windows.Markup.XamlReader]::Load($reader)
$root = $window.FindName('Root')
$bubble = $window.FindName('Bubble')
$bubbleText = $window.FindName('BubbleText')
$idleBob = $window.FindName('IdleBob')
$bounceScale = $window.FindName('BounceScale')
$bodyTilt = $window.FindName('BodyTilt')
$bodyShift = $window.FindName('BodyShift')
$wireTilt = $window.FindName('WireTilt')
$wireShift = $window.FindName('WireShift')
$leftBlink = $window.FindName('LeftBlink')
$rightBlink = $window.FindName('RightBlink')
$leftPupilBlink = $window.FindName('LeftPupilBlink')
$rightPupilBlink = $window.FindName('RightPupilBlink')
$leftPupil = $window.FindName('LeftPupil')
$rightPupil = $window.FindName('RightPupil')
$leftBrow = $window.FindName('LeftBrow')
$rightBrow = $window.FindName('RightBrow')

$screen = [System.Windows.SystemParameters]::WorkArea
$window.Left = [Math]::Max(40, $screen.Right - $window.Width - 70)
$window.Top = [Math]::Max(40, $screen.Bottom - $window.Height - 60)

$messages = @(
  'Need help? I can hover quietly.',
  'I am mostly here for tiny moral support.',
  'Right-click me when you want me gone.',
  'Double-click for a tiny wiggle.'
)

function Show-Bubble([string]$text, [int]$milliseconds = 2600) {
  $bubbleText.Text = $text
  $bubble.Visibility = 'Visible'
  $timer = New-Object Windows.Threading.DispatcherTimer
  $timer.Interval = [TimeSpan]::FromMilliseconds($milliseconds)
  $timer.Add_Tick({
    $bubble.Visibility = 'Collapsed'
    $this.Stop()
  })
  $timer.Start()
}

function Start-Wiggle {
  $anim = New-Object Windows.Media.Animation.DoubleAnimation
  $anim.From = 1.0
  $anim.To = 1.08
  $anim.Duration = [TimeSpan]::FromMilliseconds(130)
  $anim.AutoReverse = $true
  $anim.RepeatBehavior = New-Object Windows.Media.Animation.RepeatBehavior 2
  $bounceScale.BeginAnimation([Windows.Media.ScaleTransform]::ScaleXProperty, $anim)
  $bounceScale.BeginAnimation([Windows.Media.ScaleTransform]::ScaleYProperty, $anim.Clone())
}

function Start-Blink {
  $blink = New-Object Windows.Media.Animation.DoubleAnimationUsingKeyFrames
  $blink.KeyFrames.Add((New-Object Windows.Media.Animation.DiscreteDoubleKeyFrame 1.0, ([System.Windows.Media.Animation.KeyTime]::FromTimeSpan([TimeSpan]::FromMilliseconds(0)))))
  $blink.KeyFrames.Add((New-Object Windows.Media.Animation.SplineDoubleKeyFrame 0.08, ([System.Windows.Media.Animation.KeyTime]::FromTimeSpan([TimeSpan]::FromMilliseconds(70)))))
  $blink.KeyFrames.Add((New-Object Windows.Media.Animation.SplineDoubleKeyFrame 1.0, ([System.Windows.Media.Animation.KeyTime]::FromTimeSpan([TimeSpan]::FromMilliseconds(155)))))
  $leftBlink.BeginAnimation([Windows.Media.ScaleTransform]::ScaleYProperty, $blink)
  $rightBlink.BeginAnimation([Windows.Media.ScaleTransform]::ScaleYProperty, $blink.Clone())
  $leftPupilBlink.BeginAnimation([Windows.Media.ScaleTransform]::ScaleYProperty, $blink.Clone())
  $rightPupilBlink.BeginAnimation([Windows.Media.ScaleTransform]::ScaleYProperty, $blink.Clone())
}

function Start-Nod {
  $tilt = New-Object Windows.Media.Animation.DoubleAnimation
  $tilt.From = -2.2
  $tilt.To = 2.4
  $tilt.Duration = [TimeSpan]::FromMilliseconds(210)
  $tilt.AutoReverse = $true
  $tilt.RepeatBehavior = New-Object Windows.Media.Animation.RepeatBehavior 2
  $bodyTilt.BeginAnimation([Windows.Media.RotateTransform]::AngleProperty, $tilt)

  $wire = New-Object Windows.Media.Animation.DoubleAnimation
  $wire.From = 1.6
  $wire.To = -1.8
  $wire.Duration = [TimeSpan]::FromMilliseconds(260)
  $wire.AutoReverse = $true
  $wire.RepeatBehavior = New-Object Windows.Media.Animation.RepeatBehavior 2
  $wireTilt.BeginAnimation([Windows.Media.RotateTransform]::AngleProperty, $wire)
}

$root.Add_MouseLeftButtonDown({
  if ($_.ClickCount -ge 2) {
    Start-Wiggle
    Start-Nod
    Show-Bubble ($messages | Get-Random)
    return
  }
  $window.DragMove()
})

$menu = New-Object System.Windows.Controls.ContextMenu
$sayItem = New-Object System.Windows.Controls.MenuItem
$sayItem.Header = 'Say something'
$sayItem.Add_Click({ Show-Bubble ($messages | Get-Random) })
$quitItem = New-Object System.Windows.Controls.MenuItem
$quitItem.Header = 'Quit'
$quitItem.Add_Click({ $window.Close() })
[void]$menu.Items.Add($sayItem)
[void]$menu.Items.Add($quitItem)
$root.ContextMenu = $menu

$phase = 0.0
$lookX = 0.0
$lookY = 0.0
$targetLookX = 1.2
$targetLookY = 0.8
$tickCount = 0
$random = New-Object System.Random
$idle = New-Object Windows.Threading.DispatcherTimer
$idle.Interval = [TimeSpan]::FromMilliseconds(45)
$idle.Add_Tick({
  $script:phase += 0.065
  $script:tickCount += 1

  if (($script:tickCount % 42) -eq 0) {
    $script:targetLookX = $script:random.NextDouble() * 10.0 - 5.0
    $script:targetLookY = $script:random.NextDouble() * 5.0 - 2.0
  }

  if (($script:tickCount % 95) -eq 0 -and $script:random.NextDouble() -lt 0.72) {
    Start-Blink
  }

  if (($script:tickCount % 180) -eq 0 -and $script:random.NextDouble() -lt 0.55) {
    Start-Nod
  }

  $script:lookX += ($script:targetLookX - $script:lookX) * 0.13
  $script:lookY += ($script:targetLookY - $script:lookY) * 0.13

  $idleBob.Y = [Math]::Sin($script:phase) * 3.0
  $bodyShift.X = [Math]::Sin($script:phase * 0.45) * 1.2
  $bodyShift.Y = [Math]::Sin($script:phase * 0.7) * 1.0
  $bodyTilt.Angle = [Math]::Sin($script:phase * 0.33) * 1.5
  $wireShift.X = [Math]::Sin($script:phase * 0.54 + 1.8) * 1.2
  $wireShift.Y = [Math]::Sin($script:phase * 0.62 + 0.4) * 0.9
  $wireTilt.Angle = [Math]::Sin($script:phase * 0.38 + 0.8) * 1.9

  $leftPupil.SetValue([System.Windows.Controls.Canvas]::LeftProperty, 77.0 + $script:lookX)
  $leftPupil.SetValue([System.Windows.Controls.Canvas]::TopProperty, 115.0 + $script:lookY)
  $rightPupil.SetValue([System.Windows.Controls.Canvas]::LeftProperty, 139.0 + $script:lookX)
  $rightPupil.SetValue([System.Windows.Controls.Canvas]::TopProperty, 128.0 + $script:lookY)
})
$idle.Start()

$window.Add_ContentRendered({
  Show-Bubble 'Hi. I am a local paperclip pal.' 2200
})

[void]$window.ShowDialog()
